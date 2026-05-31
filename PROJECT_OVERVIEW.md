# IT_ADMIN — Проект учёта IT-инфраструктуры

**Дата обновления:** 2026-05-29  
**Версия:** Бета (Этапы A–F ✅ завершены, Этап G в работе)  
**Статус Tasks:** ✅ **ПОЛНОСТЬЮ ГОТОВА** (2026-05-29)

---

## Что это?

**Внутренний инструмент IT-администратора** для учёта:
- **Активов** — компьютеры, серверы, оборудование с МОЛ, гарантиями, инвентаризацией
- **Сотрудников** — с ролями (admin / user) и гранулярными правами CRUD на каждый ресурс
- **Задач** — назначение исполнителям с приоритетами (low/medium/high/critical) и статусами
- **Заметок & календаря** — личные события и системные (задачи, гарантии активов)
- **Категорий** — для организации заметок (системные защищены, пользовательские редактируемы)

**Модель пользователей:** 1 админ (полные права) + N исполнителей (ограниченные права по матрице permissions).

---

## 🚀 Запуск (для новой сессии)

```bash
# Terminal 1: Backend
cd /Users/nonrem/Desktop/IT_ADMIN
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd /Users/nonrem/Desktop/IT_ADMIN/frontend
npm run dev  # Vite, доступен на http://localhost:3000

# Убедиться: MongoDB запущен локально (или проверить URI в backend/core/config.py)
```

**Default login (если есть в БД):**
- Username: `admin`
- Password: (зависит от базы, обычно `admin`)

Если БД пуста — нужно создать админа вручную или через POST `/api/v1/users` (с JWT токеном от существующего админа).

---

## Тема и основные требования (из чата)

### 🎯 Приоритет: закрытие функциональных дыр

Пользователь **явно попросил** сосредоточиться на **логике и функционале**, а не на дизайне:
> "мне нужно закрыть дыры в функционале, дизайн оставим на потом, пока что реализуем логику которой не хватает"

**Следствие:** Дизайнерские улучшения (анимации, переработка панелей, цвета) — **низкий приоритет**. Функция — первая.

### 🔑 Основные требования (из чата)

1. **Гранулярные права CRUD** — администратор может давать пользователям права на каждый ресурс (assets, tasks, notes, categories): create, read, update, delete независимо.
2. **Email-инвайт вместо публичной регистрации** — админ создаёт пользователя, система генерирует логин + пароль и отправляет письмо.
3. **First-login с обязательной сменой пароля** — новый пользователь заходит, меняет пароль, добавляет телефон, видит свои права.
4. **Тёмная тема** — базовая реализована (CSS-переменные, переключатель), осталось отполировать (аудит хардкод-цветов).
5. **Страница задач (Tasks)** — ✅ **ГОТОВА** (таблица + фильтры + модалка CRUD + правила доступа).
6. **Аудит-лог всех операций** — кто что менял, когда, before/after значения.
7. **История активов** — кто передал МОЛ, когда, ремонты, перемещения.
8. **Экспорт данных** (CSV/XLSX/PDF) — вместо нынешней alert-заглушки.
9. **Пагинация** для больших таблиц (users, notes).

### ❌ Что НЕ делать

- **Не менять стек** — FastAPI + Motor + vanilla JS + Vite — всё работает хорошо
- **Не создавать общие utils-модули** — дублирование 2–3 строк допустимо (user просил)
- **Не ослаблять валидацию Pydantic** — regex, min/max — держать строго
- **Не амендить коммиты** — новые коммиты только по явному запросу
- **Не давать пользователю менять системные категории** (`is_default=True` → 403)

---

## 🏗️ Архитектурные принципы

### 1️⃣ Денормализация имён для перформанса
Когда задача ссылается на пользователя, сохраняем **и ObjectId, и полное имя**:
```javascript
// В документе Task сохраняем ОБА поля:
{
  "assigned_to": ObjectId("507f1f77bcf86cd799439011"),  // ← для связи, обновления
  "assigned_to_name": "Петров Петр"                      // ← для UI, без N+1 запросов
}

// При создании или обновлении assigned_to:
// 1. Проверяем что юзер существует
// 2. Читаем его full_name
// 3. Сохраняем в assigned_to_name
```
**Почему:** таблица из 100 задач не делает 100 запросов за именами. Синхронизация при CREATE/UPDATE.

**⚠️ Подводный камень:** если изменить full_name юзера, его имя в старых задачах **не обновится**. Это нормально (для истории), но помните!

---

### 2️⃣ Cookie-based JWT auth с автоматическим refresh
```javascript
// Все fetch с credentials: 'include' (отправляем куки)
fetch('/api/v1/tasks', {
  credentials: 'include'  // ← ОБЯЗАТЕЛЬНО, иначе куки не отправляются
})

// client.js обрабатывает 401:
// 1. Перехватываем 401 ответ
// 2. Пробуем POST /auth/refresh (тоже с credentials)
// 3. Если успех — повторяем оригинальный запрос
// 4. Если вторая 401 — редирект на #/login
```

**⚠️ Подводный камень:** **не оборачивайте в try/catch**, который может проглотить ошибку. Например:
```javascript
// ❌ НЕПРАВИЛЬНО: catch проглотит 401 перед редиректом
try {
  const resp = await fetch('/api/v1/tasks', { credentials: 'include' })
  const data = await resp.json()
} catch(e) {
  console.log('ошибка')  // ← редирект на login не произойдёт!
}

// ✅ ПРАВИЛЬНО: дать client.js обработать 401
const resp = await fetch('/api/v1/tasks', { credentials: 'include' })
if (!resp.ok) {
  // client.js уже всё обработал (refresh + retry или редирект)
}
const data = await resp.json()
```

---

### 3️⃣ Hash-роутинг на фронте (нет серверной маршрутизации)
```javascript
// URL не меняют сервер, всё в hash:
window.location.hash = '#/assets'          // ← меняет #, не отправляет запрос на сервер
window.location.hash = '#/tasks/edit/123'  // ← роут + параметр

// В main.js слушаем hash:
window.addEventListener('hashchange', () => {
  const hash = window.location.hash.slice(1) || '/dashboard'  // удаляем #
  // Парсим роут и параметры, вызываем нужную страницу
})
```

**⚠️ Подводный камень:** Vite в dev режиме проксирует `/api` на backend. Если меняли порт — обновить `vite.config.js`.

---

### 4️⃣ Trailing slash в API (обязателен для коллекций!)
```javascript
// ✅ ПРАВИЛЬНО:
GET /api/v1/assets/      // ← слэш в конце
GET /api/v1/notes/       // ← слэш в конце
GET /api/v1/categories/  // ← слэш в конце

// ❌ НЕПРАВИЛЬНО:
GET /api/v1/assets       // FastAPI вернёт 307 редирект на абсолютный URL
GET /api/v1/notes        // Редирект потеряет куки (основная ошибка в других проектах)

// GET /assets/{id} — без слэша (единичный элемент)
GET /api/v1/assets/507f1f77bcf86cd799439011
```

**Почему:** FastAPI по конфигу `redirect_slashes=False` на роутах не автоматически перенаправляет. Клиент знает про это и всегда добавляет слэш к коллекциям.

**✅ Клиент (`client.js`) уже это учитывает — не ломать!**

---

### 5️⃣ Системные цвета календаря (зарезервированы, не давать пользователям)
```javascript
// Эти цвета использует календарь, не давать в категориях:
#6b7280  // серый — для событий из Tasks
#8b5cf6  // фиолетовый — для конца гарантии Assets
#3b82f6  // синий — дефолт для Notes без категории

// При валидации category.color проверяем regex:
color: str = Field(..., pattern=r'^#[0-9a-fA-F]{6}$')  // + исключить эти цвета
```

---

### 6️⃣ Pydantic exclude_none, exclude_unset
```python
# При CREATE (исходящие None-поля не сохраняем):
task_dict = task.model_dump(exclude_none=True)  # {'title': '...', 'priority': 'medium'}
# В БД НЕ сохраняем { description: null }, пусть поле просто отсутствует

# При UPDATE (меняем только указанные поля):
update_dict = update_data.model_dump(exclude_unset=True)  # только то что пользователь отправил
db.tasks.update_one({...}, {"$set": update_dict})  # PATCH, не PUT
```

**Почему:** экономим место в БД, не создаём лишних null полей.

---

## 📊 Текущий статус по этапам

| Этап | Что | Статус | Детали |
|------|-----|--------|--------|
| **A** | Роли (backend) | ✅ ГОТОВО | `require_admin`, `is_admin()` в `backend/core/permissions.py` применены ко всем роутам |
| **B** | Permissions (гранулярные CRUD права) | ✅ ГОТОВО | Model `UserPermissions` с **4 ресурсами** × 4 действия = 16 флагов (`assets`, `tasks`, `notes`, `categories`). Users — только admin (нет в матрице). Calendar — публичный read. Проверки в каждом роуте. |
| **C** | Email-инвайт + first-login | ✅ ГОТОВО | Админ создаёт user через POST `/users`, система генерирует логин (транслит) + пароль + отправляет email. Новый user идёт на `/first-login` и меняет пароль + добавляет телефон. |
| **D** | AppState + скрытие UI | ✅ ГОТОВО | `frontend/src/state.js` с методами `can(res, act)`, `canSee(res)`, `isAdmin()`. Sidebar скрывает Users/Categories (только admin видит). Guard в `main.js` блокирует доступ по хешу. |
| **E** | Тёмная тема | ✅ БАЗОВО | CSS-переменные в `frontend/src/styles/themes.css`, `[data-theme="dark"]` на `<html>`, переключатель в Header (солнце/луна). Осталось: аудит хардкод-цветов в JS (в очереди на Волне 1). |
| **F** | Tasks страница | ✅ **ПОЛНОСТЬЮ ГОТОВА** | `frontend/src/pages/tasks.js` + `task-modal.js`: таблица 6 колонок, 4 счётчика (total, in_progress, completed, critical), 4 фильтра (status, priority, "только мои", "просрочены"), поиск, пагинация 25/стр. Modal 3 режима: add (админ), edit (админ), status (executor). Правила: админ может менять всё, исполнитель — только статус своей задачи. Тестировано. |
| **G** | Экспорт, история, аудит, пагинация, оптимизация | 🆕 ВПЕРЕДИ | 6 волн разработки в DEVELOPMENT_QUEUE.md |

---

## 💾 Структуры БД (примеры)

### User (коллекция: `users`)
```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "username": "ivanov_ivan",                    // уникальный, транслит ФИ
  "email": "ivan@company.ru",                   // уникальный, может быть null
  "full_name": "Иванов Иван",
  "phone": "+7-999-123-45-67",                  // опционально
  "hashed_password": "bcrypt(...)",             // ⚠️ именно "hashed_password", НЕ "password_hash"!
                                                // Никогда не отправляем в Response, не читаем — только bcrypt verify
  "role": "admin" | "user",                     // две роли
  "is_active": true,                            // можно ли логиниться (admin может деактивировать)
  "is_activated": false,                        // новый user до first-login
  "password_change_required": true,             // если true → редирект на /first-login
  "permissions": {                              // матрица CRUD прав (4 ресурса × 4 действия = 16 флагов)
    "assets":     { "create": false, "read": true, "update": false, "delete": false },
    "tasks":      { "create": false, "read": true, "update": true,  "delete": false },
    "notes":      { "create": true,  "read": true, "update": true,  "delete": true  },
    "categories": { "create": false, "read": true, "update": false, "delete": false }
    // ⚠️ users — НЕТ в permissions (управление юзерами только для admin)
    // ⚠️ calendar — НЕТ в permissions (агрегатор, всем доступен на чтение)
  },
  "theme": "light" | "dark",                    // опционально (future: сохранение выбора)
  "created_at": ISODate("2026-01-15T10:00:00Z"),
  "updated_at": ISODate("2026-05-29T14:30:00Z")
}
```

### Task (коллекция: `tasks`) — ✅ ГОТОВА
```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439012"),
  "title": "Заменить ОЗУ на сервере",
  "description": "В сервере Dell PowerEdge не хватает памяти...",
  "priority": "critical" | "high" | "medium" | "low",
  "status": "pending" | "in_progress" | "completed" | "cancelled",
  "task_type": "user" | "admin",                // служебное, для фильтрации
  "assigned_to": ObjectId("507f1f77bcf86cd799439011"),  // кому назначена
  "assigned_to_name": "Петров Петр",            // денормализация (для UI без N+1)
  "start_date": ISODate("2026-05-30T09:00:00Z"),
  "due_date": ISODate("2026-06-05T18:00:00Z"),
  "related_asset_id": ObjectId("..."),          // опционально
  "related_user_id": ObjectId("..."),           // опционально
  "created_by": "507f1f77bcf86cd799439000",     // ⚠️ в БД хранится, но НЕТ в Pydantic TaskCreate/Update/Response!
  "updated_by": "507f1f77bcf86cd799439000",     // ⚠️ устанавливается в routers/tasks.py:88-91, но не валидируется
  "created_at": ISODate("2026-05-29T10:00:00Z"),
  "updated_at": ISODate("2026-05-29T14:30:00Z")
}
```

**⚠️ Особенность Task модели:**
- В БД сохраняются `created_by`, `updated_by` (в `routers/tasks.py` строки 88-91)
- Но в Pydantic-моделях (TaskCreate/TaskUpdate/TaskResponse) эти поля **не описаны**
- Работает благодаря `model_config = ConfigDict(extra="allow")` в TaskResponse
- ⚠️ Если будешь добавлять историю/аудит — учти что эти поля не валидируются Pydantic-ом
- `convert_doc()` в `routers/tasks.py:22` конвертит все ObjectId в строки (важно для старых записей с `related_user_id` как ObjectId)

### Asset (коллекция: `assets`)
```javascript
{
  "_id": ObjectId("507f1f77bcf86cd799439020"),
  "name": "Ноутбук Dell Latitude",              // min 3, max 100 символов
  "inventory_number": "INV-2026-00123",         // уникальный, min 3, max 50
  "asset_type": "laptop",                       // ⚠️ asset_type, НЕ type!
                                                // Enum: laptop | desktop | monitor | printer | peripheral | mobile | other
  "serial_number": "ABCD123456",                // min 3, max 100
  "mol_user_id": "507f1f77bcf86cd799439011",    // МОЛ (опционально), строка ObjectId
  "mol_name": "Иванов Иван",                    // денормализация (опционально)
  "mac_address": "AA:BB:CC:DD:EE:FF",           // опционально, regex ^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$
  "commission_date": ISODate("2024-01-15T00:00:00Z"),  // опционально
  "warranty_months": 36,                        // опционально, 0..120
  "warranty_end_date": ISODate("2027-01-15T00:00:00Z"),  // опционально
  "status": "installed",                        // Enum: installed | in_use | repair | retired (дефолт: installed)
  "comments": "Установлен рядом с коммутатором",  // опционально (НЕ "notes"!)
  "location": "Кабинет 201",                    // опционально
  "created_at": ISODate("2026-01-15T10:00:00Z"),
  "updated_at": ISODate("2026-05-29T14:30:00Z")
}
```

**⚠️ Важные детали Asset модели (`backend/models/asset.py`):**
- Поле называется `asset_type` (НЕ `type`!) — иначе Pydantic вернёт validation error
- `AssetType` Literal: `"laptop" | "desktop" | "monitor" | "printer" | "peripheral" | "mobile" | "other"`
- `Status` Literal: `"installed" | "in_use" | "repair" | "retired"` (дефолт `installed`)
- `mac_address` имеет regex валидацию (обычный MAC формат AA:BB:CC:DD:EE:FF или AA-BB-...)
- `model_config = ConfigDict(extra="allow")` — допускается сохранять доп. поля
- Поле для заметок — `comments`, НЕ `notes` (чтобы не путать с коллекцией заметок)

---

## ⚠️ Критичные подводные камни

| Проблема | Решение | Файл |
|----------|---------|------|
| **ObjectId сериализация в JSON** | В роутах есть `convert_doc()` для замены `_id` на `id` и ObjectId → string | `backend/routers/tasks.py:22` |
| **Trailing slash теряет куки** | Клиент всегда добавляет слэш к коллекциям (`/assets/`, `/notes/`, `/categories/`) | `frontend/src/api/client.js` |
| **401 в try/catch проглатывается** | Не оборачивайте fetch в try/catch — дайте client.js обработать 401 | `frontend/src/api/client.js` |
| **Vite проксирует /api на :8000** | Если меняли порт backend — обновить `vite.config.js` | `frontend/vite.config.js` |
| **Денормализованные имена не синхронизируются** | При смене `full_name` юзера старые ссылки не обновляются (нормально, для истории) | - |
| **Системные категории защищены** | `is_default=True` → user не может редактировать/удалять, даже если админ | `backend/routers/categories.py` |
| **Permissions не кешируются** | На каждый запрос проверяются свежие права из БД (нет кеша) | `backend/core/permissions.py` |
| **Password не меняется через PUT /users/{id}** | Только `PATCH /auth/me` позволяет менять пароль (для first-login). Это в роутере `auth`, НЕ `users`! | `backend/routers/auth.py` |
| **Category использует alias для _id** | `id: str = Field(..., alias="_id")` — при сериализации БД-документа Pydantic читает `_id`, а отдаёт как `id`. `populate_by_name=True` в конфиге. | `backend/models/category.py:45` |
| **Asset поле `comments`, НЕ `notes`** | Чтобы не путать с коллекцией `notes`. При создании актива заметку класть в `comments`. | `backend/models/asset.py` |
| **Asset поле `asset_type`, НЕ `type`** | Pydantic вернёт 422 validation error если отправить `type`. | `backend/models/asset.py:13` |
| **Export.py НЕ существует** | `backend/routers/export.py` отсутствует, не подключён в `main.py`. POST `/api/v1/export` вернёт 404. В очереди на Волну 1. | DEVELOPMENT_QUEUE.md |
| **PATCH /users/me НЕ существует** | Самообслуживание — это **PATCH /auth/me**, не /users/me! Только `phone` + `password` + `password_confirm` (модель `UserSelfUpdate`). | `backend/routers/auth.py` |

---

## Ключевые файлы и соглашения

### Backend структура
```
backend/
├── main.py                    # FastAPI app, регистрация роутеров
├── core/
│   ├── database.py           # Motor async client, init_indexes (никогда не блокирует)
│   ├── security.py           # JWT генерация/проверка, get_current_user (dependency)
│   ├── permissions.py        # require_admin, is_admin, require_permission
│   ├── config.py             # переменные из .env (MONGO_URI, JWT_SECRET, SMTP_*)
│   └── logging.py            # логирование
├── models/
│   ├── user.py              # User, UserCreate, UserUpdate, UserResponse + Permissions nested
│   ├── asset.py             # Asset (с денормализованным mol_name)
│   ├── task.py              # Task (convert_doc фиксит ObjectId serialization)
│   ├── note.py              # Note (author = current_user)
│   ├── category.py          # Category (is_default=true защищена от редакции)
│   └── ...
└── routers/
    ├── auth.py              # POST /login, /logout, /refresh, GET /me
    ├── users.py             # POST/GET/PATCH/DELETE /users (admin-only, except GET /me)
    ├── assets.py            # GET (по правам), POST/PATCH/DELETE (require_admin)
    ├── tasks.py             # GET (all), POST/DELETE (admin), PUT (admin или user-executor)
    ├── notes.py             # POST (author=you), GET (свои), PATCH/DELETE (author or admin)
    ├── categories.py        # CRUD (админ), но is_default=true защищена (403)
    ├── calendar.py          # GET /events (агрегирует задачи+активы+заметки, фильтр only_mine)
    └── export.py            # POST /export (alert-заглушка, нужна реализация)
```

**Пример роута с правами (из tasks.py):**
```python
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    update_data: TaskUpdate,
    current_user: dict = Depends(get_current_user),  # ← всегда проверяем юзера
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    existing_task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not existing_task:
        raise HTTPException(404, "Задача не найдена")
    
    # Политика: admin меняет всё, user только status у свой задачи
    if not is_admin(current_user):
        assigned_to = existing_task.get("assigned_to")
        if not assigned_to or str(assigned_to) != current_user["id"]:
            raise HTTPException(403, "Можно редактировать только задачи, назначенные вам")
        # User может менять только статус
        ALLOWED_FIELDS_FOR_USER = {"status"}
        forbidden = set(update_data.model_dump(exclude_unset=True).keys()) - ALLOWED_FIELDS_FOR_USER
        if forbidden:
            raise HTTPException(403, f"Запрещённые поля: {', '.join(sorted(forbidden))}")
    
    # Остальная логика...
```

### Frontend структура
```
frontend/src/
├── main.js                   # Router (hash-роутинг), guards по правам, refreshState() при загрузке
├── state.js                  # ✅ AppState синглтон: {user, role, permissions, методы can/canSee/isAdmin}
├── pages/
│   ├── auth.js              # Форма логина (регистрация удалена в Этапе C)
│   ├── dashboard.js         # Метрики, календарь, timeline (частично заглушки)
│   ├── assets.js            # Таблица активов с пагинацией (25/стр), поиск, кнопки по правам
│   ├── tasks.js             # ✅ ГОТОВА: таблица + 4 счётчика + 4 фильтра + 25/стр пагинация
│   ├── users.js             # Таблица юзеров (видна только admin, guard в main.js)
│   ├── notes.js             # Таблица заметок (видна свои + shared)
│   ├── categories.js        # Управление категориями (видна только если rights)
│   ├── calendar.js          # Месячная сетка + события
│   ├── first-login.js       # Страница активации нового юзера (readonly data, ввод phone+пароль)
│   └── export.js            # Форма экспорта (сейчас alert-заглушка)
├── components/
│   ├── Header.js            # Breadcrumb, поиск (декоративный), переключатель темы, avatar, logout
│   ├── Sidebar.js           # Навигация (видны только вкладки по правам: Users/Categories только admin)
│   └── modals/
│       ├── asset-modal.js   # CRUD актива
│       ├── task-modal.js    # ✅ Три режима: add (админ вводит всё), edit (админ), status (executor меняет только статус)
│       ├── user-modal.js    # Создание юзера с матрицей permissions
│       ├── note-modal.js    # CRUD заметки
│       └── category-modal.js
└── api/
    └── client.js            # ✅ Единый API-клиент с 401 retry: при 401 → POST /refresh → повтор, вторая 401 → редирект на #/login
```

**Пример использования state.js на фронте (из assets.js):**
```javascript
// В таблице активов: показать кнопку "Добавить" только если есть право
const showCreateBtn = state.can('assets', 'create');  // ← returns boolean

// В строке таблицы: показать кнопку Edit только admin
const showEditBtn = state.isAdmin();

// На странице: если user не может читать активы, guard в main.js редиректит на /dashboard
// но если можно читать, но не создавать — таблица видна, кнопка "+" скрыта
```

### Pydantic модели — соглашение именования
- `*Create` — для POST (может быть без ID, timestamps)
- `*Update` — для PATCH/PUT (exclude_unset=True)
- `*Response` — для GET (полная информация, после преобразования)

**Пример (tasks.py):**
```python
class TaskCreate(BaseModel):
    title: str
    priority: TaskPriority = "medium"
    status: TaskStatus = "pending"
    # ...

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[TaskStatus] = None
    # ... (не все поля, только что может меняться)

class TaskResponse(BaseModel):
    id: str  # вместо _id
    title: str
    priority: TaskPriority
    # ... (всё, что вернётся из БД)
    model_config = ConfigDict(extra="allow")  # allow any extra fields
```

---

## Язык и стилизация

- **Язык кода:** русский (комментарии, docstrings, имена переменных внутри функций)
- **Язык интерфейса:** русский (кнопки, сообщения, заголовки)
- **Разметка:** vanilla HTML + CSS (no Tailwind, no UI frameworks)
- **Стили:** `frontend/src/styles/` — CSS с переменными для тёмной темы

---

## 📡 Справочник API эндпоинтов (основные)

```bash
# ════════════════ AUTH ════════════════
POST   /api/v1/auth/login                   # Body: {username, password}
POST   /api/v1/auth/logout
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me                      # Текущий user + permissions
PATCH  /api/v1/auth/me                      # ⚠️ Самообслуживание: phone + password (для first-login)
                                             # НЕ /users/me — этот эндпоинт в роутере auth, не users!

# ════════════════ USERS (admin-only) ════════════════
GET    /api/v1/users                        # БЕЗ trailing slash. Список (?skip=0&limit=25)
POST   /api/v1/users                        # БЕЗ trailing slash. Body: {full_name, email, phone?, permissions}
                                             # Система генерирует username (транслит) + пароль 12-сим, отправляет email
GET    /api/v1/users/{id}
PUT    /api/v1/users/{id}                   # ⚠️ PUT, не PATCH! Редактировать юзера
DELETE /api/v1/users/{id}

# ════════════════ ASSETS ════════════════
GET    /api/v1/assets                       # БЕЗ trailing slash. По правам; ?skip=0&limit=25&search=...
GET    /api/v1/assets/{id}
POST   /api/v1/assets                       # БЕЗ trailing slash. (require_admin)
PATCH  /api/v1/assets/{id}                  # ⚠️ Здесь PATCH (отличается от users/notes/categories!)
DELETE /api/v1/assets/{id}

# ════════════════ TASKS ✅ ════════════════
GET    /api/v1/tasks                        # БЕЗ trailing slash. ?task_type=user&priority=critical&assigned_to=...
GET    /api/v1/tasks/{id}
POST   /api/v1/tasks                        # (require_admin)
PUT    /api/v1/tasks/{id}                   # PUT. Admin меняет всё, user-исполнитель только status
DELETE /api/v1/tasks/{id}                   # (require_admin)

# ════════════════ NOTES ════════════════
GET    /api/v1/notes/                       # ⚠️ СО trailing slash!
GET    /api/v1/notes/{id}                   # без slash для конкретного
POST   /api/v1/notes/                       # ⚠️ СО trailing slash!
PUT    /api/v1/notes/{id}                   # ⚠️ PUT, не PATCH! Только author или admin
DELETE /api/v1/notes/{id}

# ════════════════ CATEGORIES ════════════════
GET    /api/v1/categories/                  # ⚠️ СО trailing slash!
GET    /api/v1/categories/{id}
POST   /api/v1/categories/                  # ⚠️ СО trailing slash!
PUT    /api/v1/categories/{id}              # ⚠️ PUT, не PATCH! is_default=true → 403
DELETE /api/v1/categories/{id}              # is_default=true → 403

# ════════════════ CALENDAR ════════════════
GET    /api/v1/calendar/events              # ?start=2026-05-29T00:00:00Z&end=...&only_mine=false
                                             # Агрегирует tasks + assets (warranty) + notes

# ════════════════ EXPORT 🚧 НЕ РЕАЛИЗОВАН ════════════════
# Файл backend/routers/export.py НЕ существует, в main.py не подключён.
# В очереди: Волна 1 (DEVELOPMENT_QUEUE.md). Планируется:
# POST /api/v1/export — Body: {format: "csv"|"xlsx", types: [...], date_from?, date_to?}
```

**Сводка по trailing slash и HTTP методам (важно!):**

| Роутер | Коллекция (GET/POST list) | Update | Особенность |
|--------|---------------------------|--------|-------------|
| `auth` | — | PATCH `/me` | `/me` — самообслуживание (phone+password) |
| `users` | без `/` (`/users`) | **PUT** `/{id}` | admin-only |
| `assets` | без `/` (`/assets`) | **PATCH** `/{id}` | admin-only для CUD |
| `tasks` | без `/` (`/tasks`) | **PUT** `/{id}` | admin-only для C/D, executor только status |
| `notes` | **со `/`** (`/notes/`) | **PUT** `/{id}` | author или admin |
| `categories` | **со `/`** (`/categories/`) | **PUT** `/{id}` | is_default защищены |

**Примеры curl для тестирования:**
```bash
# Логин
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}' \
  -c cookies.txt

# Получить текущего юзера (с куками)
curl http://localhost:8000/api/v1/auth/me \
  -b cookies.txt

# Создать актив (admin-only) — ВНИМАНИЕ: asset_type, не type!
curl -X POST http://localhost:8000/api/v1/assets \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name": "Ноутбук Dell", "inventory_number": "INV-001", "asset_type": "laptop", "serial_number": "SN12345"}'

# Получить задачи с фильтром
curl "http://localhost:8000/api/v1/tasks?priority=critical&status=pending" \
  -b cookies.txt

# Самообслуживание: сменить пароль (first-login)
curl -X PATCH http://localhost:8000/api/v1/auth/me \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"phone": "+7-999-123-45-67", "password": "newpass123", "password_confirm": "newpass123"}'

# Создать заметку (со слэшем!)
curl -X POST http://localhost:8000/api/v1/notes/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"title": "Совещание", "event_start": "2026-05-30T10:00:00Z"}'
```

---

## Что дальше? (Волны разработки)

1. **Волна 1 (1–2 часа):** Экспорт, тёмная тема (отполировать), пагинация users/notes
2. **Волна 2 (2–3 часа):** История актива, снапшоты метрик
3. **Волна 3 (2–3 часа):** Аудит-лог (базовый)
4. **Волна 4 (2–4 часа):** Toast-уведомления, вкладка Настройки, быстрое создание
5. **Волна 5 (1–2 часа):** Аналитика активности (эндпоинт + график)
6. **Волна 6+ (future):** Уведомления, поиск, сортировка, комментарии, импорт, файлы, мобильная адаптация

**Детальный порядок:** смотри **DEVELOPMENT_QUEUE.md**.
