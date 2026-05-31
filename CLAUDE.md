# IT_ADMIN — система учёта IT-инфраструктуры

Внутренний инструмент IT-администратора: учёт активов, сотрудников, задач,
заметок и календарь событий. Один админ + сотрудники-исполнители задач.

## Стек

- **Backend:** FastAPI + Motor (async MongoDB), Pydantic v2, JWT в cookie.
- **Frontend:** vanilla JS SPA + **Alpine.js 3.x** (декларативный слой),
  Vite, hash-роутинг.
- **БД:** MongoDB. Коллекции: `users`, `assets`, `tasks`, `notes`,
  `categories`, `audit_log`.
- **Язык интерфейса и комментариев в коде:** русский.

## Структура

- `backend/main.py` — точка входа, регистрация роутеров.
- `backend/routers/` — `auth`, `users`, `assets`, `tasks`, `notes`,
  `categories`, `calendar`, `export`, `audit`. Префикс всех — `/api/v1/...`.
- `backend/core/audit.py` — единый аудит-лог: `log_action()`,
  `diff_changes()`, `snapshot()` (см. ниже).
- `backend/models/` — Pydantic-модели (`*Create`, `*Update`, `*Response`).
- `backend/core/` — `database.py` (Motor-клиент + `init_indexes`),
  `security.py` (JWT, `get_current_user`), `config.py`, `logging.py`.
- `frontend/src/main.js` — Router (хеш-роутинг), Alpine.start().
- `frontend/src/api/client.js` — единый API-клиент, объекты по сущностям.
- `frontend/src/pages/<name>/` — на каждую страницу/модалку папка из двух
  файлов: `<name>.html` (разметка + Alpine-биндинги) и `<name>.js`
  (`Alpine.data(...)` + `renderXPage()` возвращает импортированный шаблон).
- `frontend/src/components/<Name>/` — то же для `Header`, `Sidebar`, `Modal`.
- `frontend/src/components/app-layout.html` — корневая обёртка
  Sidebar + container + main-content.

## Правило диплома: «никакого HTML в JS»

- В `.js` файлах **запрещены** template literals с HTML (`` `<div>...` ``),
  `el.innerHTML = '<...>'`, любые конкатенации тегов.
- Разметка живёт в `.html`-файлах. JS импортирует строкой через Vite:
  `import tpl from './foo.html?raw'`.
- Для нескольких видов формы (add/edit/success) — `<template id="...">` теги
  внутри одного `.html`, `tpl.content.cloneNode(true)`.
- Заполнение данных: только DOM API (`querySelector`, `el.textContent`,
  `el.value`, `appendChild(document.createElement(...))`).
- Иконки (`components/icons.js`) — инфраструктурные SVG-ассеты, вставляются
  в шаблон через `x-html="Icons.foo()"`. Это исключение, не повод
  возвращать template literals в логику страниц.

## Alpine-паттерн страницы

```js
import Alpine from 'alpinejs';
import tpl from './page.html?raw';

Alpine.data('pageName', () => ({
  // state, getters, methods, init()
}));

export async function renderPageName() { return tpl; }
export function initPageNameEvents() {}  // заглушка для роутера
```

В `.html`: `<div x-data="pageName" x-init="init()">...</div>`.
Alpine инициализирует компонент при вставке через `innerHTML`.

## Ключевые сущности

- **Asset** — актив. Поле `asset_type` (НЕ `type`!):
  `laptop|desktop|monitor|printer|peripheral|mobile|other`.
  Статус: `installed|in_use|repair|retired` (дефолт `installed`).
  Поля: `mol_user_id` + денормализованный `mol_name` (МОЛ), `commission_date`,
  `warranty_end_date`, `warranty_months`, `inventory_number` (uniq),
  `mac_address` (regex MAC), `comments` (НЕ `notes`!).
- **Task** — задача сотруднику. `priority` (low/medium/high/critical),
  `status` (pending/in_progress/completed/cancelled),
  `task_type` (user/admin), `assigned_to` + денормализованный
  `assigned_to_name`, `start_date`, `due_date`, `related_asset_id`,
  `related_user_id`.
- **Note** — заметка/событие пользователя. `event_start`, `event_end`,
  `category_id`, `created_by`, может ссылаться на актив/пользователя.
- **Category** — категория заметок. `owner_id=None` → системная (видна
  всем, не редактируется/не удаляется), `is_default=True` блокирует
  изменения. Цвет хранится в hex (`^#[0-9a-fA-F]{6}$`).
- **AuditLog** (`audit_log`) — единый журнал действий. Поля: `timestamp`,
  `actor_id` (None → системная операция), `actor_name` (денорм. username
  или «Система»), `action` (`create|update|delete`), `entity_type`
  (`asset|user|task|note|category`), `entity_id`, `entity_label`
  (денорм. подпись), `before`/`after`. ЗАПИСИ ТОЛЬКО ЧЕРЕЗ
  `core/audit.py:log_action()` — НЕ писать в коллекцию руками.

## Соглашения

- **Денормализация имён:** при ссылке на пользователя/актив дублируем
  отображаемое имя в документ (`mol_name`, `assigned_to_name`), чтобы
  список не делал N лишних запросов.
- **Trailing slash в API:** для коллекционных эндпоинтов
  (`/notes/`, `/categories/`) обязателен слэш в конце — без него FastAPI
  возвращает 307 redirect на абсолютный URL и теряет куки. В клиенте
  это уже учтено, не ломать.
- **Auth:** cookie-based, `credentials: 'include'` во всех fetch.
  401 → `client.js` делает один автоматический `refresh` и повторяет
  запрос, при второй неудаче — редирект на `#/login`.
- **Системные цвета календаря (зарезервированы, не использовать в
  пользовательских категориях):**
  - `#6b7280` — задачи
  - `#8b5cf6` — конец гарантии активов
  - `#3b82f6` — дефолт заметок без категории
- **Календарь** (`GET /api/v1/calendar/events?start=&end=`) — агрегирует
  три источника: задачи, активы (commission/warranty), заметки. Каждое
  событие имеет `source`, `type`, `date`, `link`, `related_id`.
- **Аудит-лог — единый источник.** И страница `/audit` (admin-only),
  и вкладка «История» в модалке актива читают из ОДНОЙ коллекции
  `audit_log` через `GET /api/v1/audit`. История актива = фильтр
  `?entity_type=asset&entity_id=<id>`. В CRUD-обработчиках после
  insert/update/delete вызываем `await log_action(db, actor=current_user,
  action=..., entity_type=..., entity_id=..., entity_label=...,
  before/after=...)`. Для update передаём дифф изменённых полей
  (`diff_changes(old, update_dict)` → пишем только если `after` непустой);
  для create/delete — `snapshot(doc)`. `log_action` НИКОГДА не роняет
  основную операцию (ошибки записи глушатся в warning).
- **Сортировка категорий:** системные первыми (`is_default=True`),
  потом личные по алфавиту.
- **Серверная сортировка таблиц:** `?sort_by=&sort_order=`.
  Список разрешённых полей — в роутере (`_ALLOWED_SORT_FIELDS`),
  любые другие значения молча сбрасываются в дефолт. Индексы
  по этим полям сейчас НЕ создаём — записей мало (<50 на сущность).
- **Серверная пагинация:** `?skip=&limit=` + заголовок `X-Total-Count`.
  На фронте `api.getPaginated(url)` → `{ items, total }`.
- **Кликабельные стрелки сортировки** в `<th>` — паттерн
  `setSort(field)` + `sortArrow(field)` в Alpine компоненте,
  отображение через `<span class="sort-arrow" x-text="sortArrow('...')">`.

## Известные подводные камни

- В `tasks.py` есть `convert_doc()`: `_id` нужно убирать, иначе
  `TaskResponse(**doc)` падает (модель не знает поле `_id`).
- `redirect_slashes=False` стоит на роутерах, где slash в URL значим.
- В `frontend/src/api/client.js` ловится 401 — не оборачивать запросы
  в свой try/catch, который проглатывает ошибку до редиректа на login.
- Vite dev-сервер проксирует `/api` на backend. Если меняли порт —
  смотреть `vite.config.js`.
- **Модалки: `buildBody()` ВОЗВРАЩАЕТ DOM-узел, а не `.innerHTML`-строку.**
  `.value` / `.selected` / `.checked` — это DOM-свойства, они НЕ
  сериализуются в строку (в HTML отражаются только атрибуты
  `defaultValue`/`defaultSelected`). Если вернуть `root.innerHTML`, форма
  редактирования откроется пустой. `openModal({ body })` и `ctl.setBody()`
  принимают и строку, и `Node` — для заполненных форм всегда передаём узел.

## Запуск (dev)

- Backend: из корня — `uvicorn backend.main:app --reload`.
- Frontend: `cd frontend && npm run dev`.
- MongoDB должен быть запущен локально (URI в `backend/core/config.py`).

## Чего не делать

- Не возвращать HTML в JS (см. правило диплома выше). Любая разметка
  только через `.html` + Vite `?raw`.
- Не создавать общие helpers/utils-модули «на будущее» — пользователь
  отклонил такое предложение раньше. Дублирование 2–3 строк
  (например, `escapeHtml` — теперь и не нужен, его роль играет
  `textContent` / Alpine `x-text`) допустимо.
- Не ослаблять валидацию Pydantic (regex на hex, min/max length).
- Не давать пользователю править/удалять системные категории
  (`is_default=True` → 403). Эта защита в `routers/categories.py`.
- Не добавлять индексы Mongo «на всякий случай» — записей мало,
  серверная сортировка обходится `collscan + sort`.
- Не амендить коммиты, коммитить только по явному запросу.
