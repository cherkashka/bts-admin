# ARCHITECTURE — Функциональные блоки и зависимости

**Для:** новых сессий Claude, чтобы понять зоны ответственности, зависимости и API контракты.

---

## Frontend: архитектура (Alpine.js + .html шаблоны)

**Принцип:** в `.js` файлах **нет HTML**. Любая разметка живёт в `.html`,
импортируется в JS строкой через Vite `?raw`.

### Структура каталогов

```
frontend/src/
├── main.js                          # роутер, импорт Alpine + страниц
├── api/client.js                    # fetch-обёртка, api.getPaginated()
├── state.js                         # AppState (user, permissions)
├── components/
│   ├── app-layout.html              # корневой layout (sidebar + container)
│   ├── icons.js                     # SVG-ассеты (исключение из правила)
│   ├── Header/{Header.html,.js}     # Alpine.data('appHeader')
│   ├── Sidebar/{Sidebar.html,.js}   # Alpine.data('appSidebar')
│   └── Modal/{Modal.html,.js}       # helper openModal/closeModal
├── pages/
│   ├── <page>/<page>.{html,js}      # assets, users, tasks, notes, calendar,
│   │                                # categories, export, dashboard, auth,
│   │                                # first-login
│   └── <page>-modal/<page>-modal.{html,js}
│                                    # asset, user, task, note, category
└── styles/                          # CSS, общий для всех страниц
```

### Паттерн страницы

`page.html`:
```html
<div x-data="pageName" x-init="init()">
  <h2 class="content-title">…</h2>
  <input type="search" x-model="search">
  <template x-for="item in visibleItems" :key="item.id">
    <tr><td x-text="item.title"></td></tr>
  </template>
</div>
```

`page.js`:
```js
import Alpine from 'alpinejs';
import tpl from './page.html?raw';
import { api } from '../../api/client.js';

Alpine.data('pageName', () => ({
  items: [], search: '',
  get visibleItems() { /* фильтрация */ },
  async init() { this.items = await api.get('/things'); },
}));

export async function renderPageName() { return tpl; }
export function initPageNameEvents() {}
```

`main.js` вставляет `tpl` в `#main-content` через `innerHTML`,
Alpine инициализирует `x-data` через MutationObserver.

### Паттерн модалки

- Шаблон формы — `<page>-modal/<page>-modal.html` (для add/edit/success
  — три `<template id="…">` внутри одного файла).
- `<page>-modal.js`: `cloneNode(true)` нужного шаблона, заполнение values
  через `el.value = …`, `appendChild(document.createElement('option'))`.
  Результирующий `root.innerHTML` отдаётся в `openModal({ body })`.
- `components/Modal/Modal.js` клонирует обёртку из `Modal.html`,
  вставляет переданный `body` и выдаёт контроллер `ctl` с
  `form/bodyEl/setError/close/hideSubmit/setBody`.

### Серверная сортировка + пагинация

Любой list-эндпоинт принимает:
- `?skip=&limit=` — пагинация (фронт: `api.getPaginated(url)` → `{ items, total }`).
- `?sort_by=&sort_order=` — сортировка, allow-list полей `_ALLOWED_SORT_FIELDS`
  в каждом роутере.

На стороне фронта (Alpine):
```js
setSort(field) {
  if (this.sortBy === field) this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
  else { this.sortBy = field; this.sortOrder = 'asc'; }
  this.page = 1; this.load();
}
sortArrow(field) {
  if (this.sortBy !== field) return '↕';
  return this.sortOrder === 'asc' ? '↑' : '↓';
}
```

В шаблоне:
```html
<th class="th-sortable" @click="setSort('name')">
  Название <span class="sort-arrow" x-text="sortArrow('name')"></span>
</th>
```

---

## Функциональные блоки системы

### 🔐 **Блок 1: Authentication & Authorization**

**Зона ответственности:**
- Вход/выход (login, logout, refresh token)
- Cookie-based JWT сессии
- Проверка прав доступа (is_admin, require_admin, require_permission)

**API Endpoints:**
```bash
# Login
POST /api/v1/auth/login
Body: { "username": "admin", "password": "..." }
Response: { "access_token": "jwt...", "token_type": "bearer", "user": {...} }
Cookies: Set-Cookie: access_token=jwt...; HttpOnly; SameSite=Lax

# Get current user (требует auth)
GET /api/v1/auth/me
Response: { "id": "...", "username": "...", "role": "admin", "permissions": {...} }

# Refresh token
POST /api/v1/auth/refresh
Response: { "access_token": "new_jwt..." }

# Logout
POST /api/v1/auth/logout
Response: { "message": "Logged out" }
Cookies: Set-Cookie: access_token=; Max-Age=0
```

**Компоненты:**
- `backend/routers/auth.py` — эндпоинты выше
- `backend/core/security.py` — функции:
  - `create_access_token(data)` — создание JWT
  - `verify_token(token)` — проверка и распаковка JWT
  - `get_current_user(token)` — dependency, используется в роутах
  - `get_current_user_or_none(token)` — для опциональной auth
- `backend/core/permissions.py` — dependencies:
  - `require_admin` — проверяет `is_admin()`, иначе 403
  - `is_admin(current_user)` — хелпер функция
  - `require_permission(resource, action)` — гранулярная проверка (future)
- `frontend/pages/auth.js` — форма логина (HTML + обработчики)
- `frontend/api/client.js` — обёртка fetch с 401 retry logic

**Пример использования в роуте:**
```python
@router.get("/api/v1/tasks")
async def get_tasks(
    current_user: dict = Depends(get_current_user),  # ← требует auth
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    # current_user = { "id": "...", "username": "admin", "role": "admin", "permissions": {...} }
    if not is_admin(current_user):  # ← дополнительная проверка
        raise HTTPException(403, "Only admin can access this")
    # ...
```

**Зависимости (входящие):**
- MongoDB (список юзеров для проверки credential)
- Config (JWT_SECRET, ALGORITHM)

**Зависимости (исходящие):**
- User Management (получение permissions юзера)
- All Other Routers (каждый использует `Depends(get_current_user)`)

**Открытые вопросы:**
- Нужна ли двухфакторная аутентификация?
- Timeout сессии (сейчас нет, вечная)?

---

### 👥 **Блок 2: User Management**

**Зона ответственности:**
- CRUD пользователей (только админ)
- Создание пользователя с email-инвайтом
- Роли (admin / user) и гранулярные права (permissions CRUD на каждый ресурс)
- First-login (активация, смена пароля, добавление телефона)
- Деактивация пользователей

**Компоненты:**
- `backend/routers/users.py` — `POST`, `GET`, `PATCH`, `DELETE` (все admin-only)
- `backend/models/user.py` — User, UserCreate, UserPermissions, UserResponse
- `backend/core/mailer.py` — SMTP отправка email-инвайтов
- `backend/templates/welcome_email.html` — шаблон письма
- `frontend/pages/users.js` — таблица сотрудников (admin-only)
- `frontend/components/user-modal.js` — форма создания/редактирования
- `frontend/pages/first-login.js` — страница активации для новых юзеров
- `frontend/api/client.js` — API методы для users

**Структура User в БД:**
```javascript
{
  _id: ObjectId,
  username: "ivanov_ivan",
  email: "ivan@example.com",
  full_name: "Иванов Иван",
  phone: "+7-999-123-45-67",
  role: "user" | "admin",
  hashed_password: "...",                 // ⚠️ именно hashed_password (НЕ password_hash)
  is_active: true,
  is_activated: false,
  password_change_required: true,
  permissions: {                          // ⚠️ только 4 ресурса × 4 действия = 16 флагов
    assets:     { create, read, update, delete },
    tasks:      { create, read, update, delete },
    notes:      { create, read, update, delete },
    categories: { create, read, update, delete }
    // users — НЕТ (только admin может)
    // calendar — НЕТ (агрегатор, всем read доступен)
  },
  created_at, updated_at
}
```

**Зависимости (входящие):**
- Authentication (проверка прав админа)
- Mailer (отправка инвайтов)

**Зависимости (исходящие):**
- Все блоки (проверка прав: `state.can(resource, action)`)

**Открытые вопросы:**
- SMTP-провайдер: Gmail App Password / Brevo / Mailtrap?
- Дефолтные permissions при создании: только read везде / всё OFF / пресет?
- Логин: автогенерация транслитерации или админ вручную?
- На first-login: менять ли ФИО/email или только phone?

---

### 📦 **Блок 3: Asset Management**

**Зона ответственности:**
- CRUD активов (по правам: админ полностью, user — по правам)
- Привязка МОЛ (материально-ответственное лицо — пользователь)
- Гарантии, инвентаризация
- История изменений активов (future)

**Компоненты:**
- `backend/routers/assets.py` — GET (by permissions), POST/PATCH/DELETE (admin)
- `backend/models/asset.py` — Asset, AssetCreate, AssetUpdate, AssetResponse
- `frontend/pages/assets.js` — таблица активов с пагинацией
- `frontend/components/asset-modal.js` — CRUD форма

**Структура Asset в БД** (см. `backend/models/asset.py`):
```javascript
{
  _id: ObjectId,
  name: "Ноутбук Dell Latitude",       // min 3, max 100
  inventory_number: "INV-00123",        // unique, min 3, max 50
  asset_type: "laptop",                 // ⚠️ asset_type, НЕ type
                                        // Enum: laptop|desktop|monitor|printer|peripheral|mobile|other
  serial_number: "ABC123",              // min 3, max 100
  mol_user_id: "<string ObjectId>",     // опционально
  mol_name: "Иванов Иван",              // денормализация, опционально
  mac_address: "AA:BB:CC:DD:EE:FF",     // опционально, regex MAC
  commission_date: ISODate,             // опционально
  warranty_months: 24,                  // опционально, 0..120
  warranty_end_date: ISODate,           // опционально
  status: "installed",                  // Enum: installed|in_use|repair|retired (дефолт installed)
  comments: "...",                      // ⚠️ comments, НЕ notes (чтобы не путать с коллекцией notes)
  location: "Кабинет 201",              // опционально
  created_at, updated_at
}
```

**Зависимости (входящие):**
- User Management (проверка МОЛ существует)
- Authorization (check `assets:create`, `assets:update` и т.д.)

**Зависимости (исходящие):**
- Calendar (события гарантий)
- Audit Log (логирование смены МОЛ)
- Asset History (future)

**Открытые вопросы:**
- Как отслеживать ремонты и обслуживание?
- Фото/документы активов (future)?

---

### ✅ **Блок 4: Task Management**

**Зона ответственности:**
- CRUD задач (админ создаёт, user — обновляет только статус)
- Приоритеты: low/medium/high/critical
- Статусы: pending/in_progress/completed/cancelled
- Привязка исполнителя, актива, пользователя
- Фильтры и поиск

**Компоненты:**
- `backend/routers/tasks.py` — POST/DELETE (admin), GET (all), PUT (admin или user-executor на свой статус)
- `backend/models/task.py` — Task, TaskCreate, TaskUpdate, TaskResponse
- `frontend/pages/tasks.js` — таблица + 4 счётчика + 4 фильтра (статус, приоритет, "только мои", "просрочены") + поиск
- `frontend/components/task-modal.js` — три режима: add (админ), edit (админ), status (executor)

**Статус реализации:** ✅ **ГОТОВО** (2026-05-29)

**Структура Task в БД:**
```javascript
{
  _id: ObjectId,
  title: "Заменить ОЗУ на сервере",
  description: "...",
  priority: "critical" | "high" | "medium" | "low",
  status: "pending" | "in_progress" | "completed" | "cancelled",
  task_type: "user" | "admin",
  assigned_to: ObjectId (User),
  assigned_to_name: "Петров Петр", // денормализация
  start_date: ISODate,
  due_date: ISODate,
  related_asset_id: ObjectId (Asset),
  related_user_id: ObjectId (User),
  created_by: ObjectId (User),
  created_at, updated_at
}
```

**Зависимости (входящие):**
- User Management (check assigned_to, created_by)
- Asset Management (check related_asset_id)
- Authorization (check `tasks:create`, `tasks:update`)

**Зависимости (исходящие):**
- Calendar (события задач)
- Notifications (future — напоминания о дедлайнах)
- Audit Log (логирование создания, изменений, удаления)

**Открытые вопросы:**
- Комментарии к задачам (future)?
- Уведомления при назначении (future)?

---

### 📝 **Блок 5: Notes & Calendar**

**Зона ответственности:**
- CRUD заметок/событий (по правам, user видит свои)
- Категории заметок (системные + пользовательские)
- Агрегированный календарь (события из задач, активов, заметок)
- Повторяющиеся события (future)

**Компоненты:**
- `backend/routers/notes.py` — POST: author=current_user, GET (own+shared), PUT/DELETE (author or admin)
- `backend/routers/categories.py` — CRUD (admin bypass), защита системных (`is_default=true`)
- `backend/routers/calendar.py` — GET /calendar/events (агрегирует 3 источника + фильтр `only_mine`)
- `backend/models/note.py` — Note, NoteCreate, NoteUpdate, NoteResponse
- `backend/models/category.py` — Category, CategoryCreate, CategoryUpdate, CategoryResponse
- `frontend/pages/notes.js` — таблица/модалка создания
- `frontend/pages/categories.js` — управление категориями
- `frontend/pages/calendar.js` — месячная сетка + события

**Система цветов (зарезервированы):**
```
#6b7280 — задачи
#8b5cf6 — гарантии активов
#3b82f6 — дефолт заметок
```

**Зависимости (входящие):**
- User Management (check author, permissions)
- Task Management (события в календаре)
- Asset Management (события гарантий в календаре)
- Authorization

**Зависимости (исходящие):**
- Notifications (future)

---

### 🎨 **Блок 6: UI & Theme**

**Зона ответственности:**
- Глобальное состояние AppState (`state.js`)
- Переключение тёмной/светлой темы
- Видимость элементов UI по правам пользователя

**Компоненты:**
- `frontend/src/state.js` — AppState с методами `can(resource, action)`, `canSee(resource)`, `isAdmin()`
- `frontend/src/styles/themes.css` — CSS-переменные для обеих тем
- `frontend/components/Header.js` — переключатель темы (солнце/луна)
- `frontend/main.js` — инициализация state, route guards

**Зависимости (входящие):**
- Authentication (get current user data)
- User Management (get permissions)

**Зависимости (исходящие):**
- All Pages (каждая страница проверяет `state.can()`)

---

### 📊 **Блок 7: Dashboard & Analytics**

**Зона ответственности:**
- Метрические карточки (активные задачи, закрытые, запланированные, критические)
- График активности (создано/закрыто задач по дням)
- Timeline/Gantt задач на 21 день
- Расписание (события из календаря)

**Компоненты:**
- `frontend/pages/dashboard.js` — renderMetrics, renderActivityCard, renderTimeline, renderSchedule
- `backend/routers/analytics.py` (future) — `/analytics/activity?days=N`

**Статус:** Частичная заглушка (события из календаря работают, метрики захардкожены)

**Заглушки:**
- Метрические значения и тренды захардкожены
- Спарклайны — синусоиды вместо реальных данных
- График активности — захардкожены
- Расписание — фильтр по дням не работает

**Зависимости (входящие):**
- Task Management (получение задач)
- Asset Management (гарантии)
- Notes & Calendar (события)

**Зависимости (исходящие):**
- Metrics Snapshots (future — для трендов)

---

### 📤 **Блок 8: Export**

**Зона ответственности:**
- Экспорт активов, задач, сотрудников в CSV/XLSX/PDF

**Компоненты:**
- `backend/routers/export.py` — POST /export (формат, диапазон дат, типы)
- `frontend/pages/export.js` — форма выбора параметров

**Статус:** Alert-заглушка (не реализовано)

**Зависимости (входящие):**
- Asset Management (список активов)
- Task Management (список задач)
- User Management (список пользователей)
- Authorization (admin-only)

---

### 🔍 **Блок 9: Audit & History** (future)

**Зона ответственности:**
- Логирование всех операций (кто, что, когда, before/after)
- История активов (смена МОЛ, ремонты, перемещения)

**Компоненты (future):**
- `backend/routers/audit.py` — GET /audit-logs (фильтры по дате, юзеру, типу)
- `backend/models/audit_log.py` — AuditLog (user_id, action, entity_type, entity_id, before, after, created_at)
- `backend/models/asset_history.py` — AssetHistory (asset_id, event_type, old_value, new_value, user_id)

**Зависимости (исходящие в другие блоки):**
- Все операционные блоки (CREATE/UPDATE/DELETE должны логировать)

---

## Матрица зависимостей

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│  Authentication ◄────────────┐                                   │
│       ▲                      │                                    │
│       │                      │                                    │
│  User Management ◄─── Authorization ◄──────┐                     │
│       ▲ ▼                         ▲          │                    │
│       │ │                         │          │                    │
│  Asset ─┤─► Calendar ◄────────────┤──────┐  │                    │
│  Management          │              │     │  │                   │
│       ▲              │              │     │  │                   │
│       │              ▼              │     │  │                    │
│  Task Management ─► Notifications  │     │  │                    │
│       │              │              │     │  │                   │
│       ▼              ▼              ▼     ▼  │                    │
│  [All Routers] ─────────────► Audit Log   │  │                   │
│                                    │      │  │                    │
│  Dashboard ◄────────────────────────┘     │  │                   │
│       │                                   │  │                    │
│       ▼                                   │  │                    │
│  Metrics Snapshots (future) ◄─────────────┘  │                   │
│                                              │                    │
│  Export ◄──────────────────────────────────┘ │                   │
│                                              │                    │
│  UI & Theme ◄──────────────────────────────┘ │                   │
│                                               │                    │
└───────────────────────────────────────────────┘
```

**Правила:**
- ✅ Стрелка → означает "зависит от"
- Блоки выше, как правило, **независимы** от блоков ниже
- Нижние блоки могут зависеть от верхних, но не наоборот

---

## Открытые архитектурные вопросы

1. **Notifications** — как уведомлять об изменениях?
   - WebSocket (real-time, но сложнее)
   - Polling (простой, но медленнее)
   - SSE (middle ground)

2. **Metrics Snapshots** — как часто снимать снимки?
   - Раз в час, в день, в неделю?
   - Где хранить (MongoDB, временный)

3. **Caching** — кешировать ли expensive запросы?
   - Список юзеров (редко меняется)
   - Список категорий (редко меняется)

4. **API Rate Limiting** — нужен ли лимит на запросы?
   - Для экспорта (большие выборки)
   - Для analytics

5. **File Storage** — как хранить вложения (future)?
   - Локальная папка
   - S3-compatible
   - Base64 в MongoDB (для маленьких)
