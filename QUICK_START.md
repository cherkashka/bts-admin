# 🚀 QUICK_START для новых сессий Claude

**Если ты в новой сессии и хочешь понять контекст проекта — читай в таком порядке:**

---

## 📋 Чек-лист: что прочитать перед работой

- [ ] **1. Этот файл** (ты здесь) — ориентация за 5 минут
- [ ] **2. PROJECT_OVERVIEW.md** (36 KB) — полный контекст проекта, все подводные камни
- [ ] **3. ARCHITECTURE.md** (20 KB) — если нужно понять зависимости между блоками
- [ ] **4. DEVELOPMENT_QUEUE.md** (20 KB) — если нужно понять что делать дальше
- [ ] **5. CLAUDE.md** (6 KB) — стек, структура репо, известные подводные камни

**Время на чтение:** ~30 минут на всё.

---

## 🎯 Что это за проект?

**IT_ADMIN** — система учёта IT-инфраструктуры (активы, сотрудники, задачи, события).

- **Стек:** FastAPI + Motor (async MongoDB), vanilla JS + Vite, hash-роутинг
- **Юзеры:** 1 админ + N исполнителей
- **Статус:** Этапы A–F ✅ готовы (Tasks полностью готова), Этап G в очереди

---

## 💾 БД: где всё хранится

```
MongoDB (локальный, URI в backend/core/config.py)
├── users          — юзеры с permissions матрицей
├── assets         — активы (ПК, серверы, оборудование) с МОЛ
├── tasks          — задачи с приоритетами и статусами ✅ ГОТОВА
├── notes          — заметки пользователей
├── categories     — категории заметок
├── [future]
│   ├── audit_logs     — логирование всех операций
│   ├── asset_history  — история смены МОЛ, перемещений
│   └── metrics_snapshots  — ежедневные снимки метрик для трендов
```

---

## 🔑 Главные требования пользователя

1. ✅ **Закрывать функциональные дыры, не дизайн** (Tasks готова, следующие: экспорт, пагинация)
2. ✅ **Гранулярные права CRUD** — админ может давать юзерам права на каждый ресурс (assets, tasks, notes…)
3. ✅ **Email-инвайт** — админ создаёт юзера, система отправляет письмо с логином+паролем
4. ✅ **Тёмная тема** — базовая готова, осталось отполировать хардкод-цвета
5. ✅ **Tasks страница** — таблица + фильтры + модалка (ПОЛНОСТЬЮ ГОТОВА)
6. 🔜 **Аудит-лог** — логирование всех операций (в очереди на Волне 3)
7. 🔜 **История активов** — отслеживание смены МОЛ и т.д. (Волна 2)
8. 🔜 **Экспорт CSV/XLSX** — вместо alert-заглушки (Волна 1)

**Что НЕ трогать:** стек (FastAPI, Motor, vanilla JS) — всё хорошо работает.

---

## 🏃 Как запустить

```bash
# Terminal 1: Backend
cd /Users/nonrem/Desktop/IT_ADMIN
uvicorn backend.main:app --reload  # Запустит на localhost:8000

# Terminal 2: Frontend
cd /Users/nonrem/Desktop/IT_ADMIN/frontend
npm run dev  # Запустит на http://localhost:3000 (Vite)

# Убедиться: MongoDB запущен (по умолчанию localhost:27017)
```

Откроешь браузер → http://localhost:3000 → форма логина.

---

## 📚 Где что находится

| Что | Где | Что искать |
|-----|-----|-----------|
| **Роуты (API)** | `backend/routers/` | `auth.py`, `users.py`, `assets.py`, `tasks.py`, `notes.py`, `categories.py`, `calendar.py` |
| **Модели БД** | `backend/models/` | `user.py`, `asset.py`, `task.py`, `note.py`, `category.py` |
| **Права доступа** | `backend/core/permissions.py` | `require_admin`, `is_admin()`, `require_permission()` |
| **Аутентификация** | `backend/core/security.py` | JWT, `get_current_user()` |
| **Страницы (UI)** | `frontend/src/pages/` | `auth.js`, `dashboard.js`, `assets.js`, `tasks.js` (✅ готова), `users.js`, `notes.js`, `calendar.js` |
| **Компоненты UI** | `frontend/src/components/` | `Header.js` (навигация, тема), `Sidebar.js` (меню по правам) |
| **Глобальное состояние** | `frontend/src/state.js` | `can(resource, action)`, `canSee(resource)`, `isAdmin()` |
| **API клиент** | `frontend/src/api/client.js` | единый fetch с 401 retry, методы для CRUD |

---

## 🚨 Критичные подводные камни

### 1. Trailing slash в API (ОБЯЗАТЕЛЕН для коллекций!)
```javascript
✅ GET /api/v1/notes/       // ← слэш!
❌ GET /api/v1/notes        // ← FastAPI вернёт 307, потеряет куки
```

### 2. Cookie-based JWT в fetch
```javascript
fetch('/api/v1/tasks', {
  credentials: 'include'  // ← ОБЯЗАТЕЛЬНО
})
```

### 3. Не оборачивайте fetch в try/catch
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
const data = await resp.json()
```

### 4. ObjectId сериализация
Роуты используют `convert_doc()` для замены `_id` на `id` перед отправкой JSON (иначе Pydantic не сможет сериализировать ObjectId).

### 5. Денормализованные имена не синхронизируются
Когда сохраняем `assigned_to_name`, он **не обновляется** если юзер изменит full_name (для истории это нормально).

### 6. Системные категории защищены
Категории с `is_default=True` не могут быть отредактированы/удалены (даже админом) — защита в роуте.

---

## 📊 Текущее состояние (2026-05-29)

| Что | Статус | Детали |
|-----|--------|--------|
| Authentication | ✅ | JWT в cookies, 401 retry |
| User Management | ✅ | CRUD, email-инвайт, first-login, permissions matrix |
| Assets | ✅ | CRUD, пагинация, МОЛ, гарантии |
| **Tasks** | ✅ **ГОТОВА** | Таблица, фильтры, модалка (add/edit/status), пагинация, 4 счётчика |
| Notes & Calendar | ✅ | CRUD, categories, агрегированный календарь |
| UI & Theme | ✅ | Тёмная тема базово, AppState, скрытие UI по правам |
| Dashboard | ⚠️ | Метрики захардкожены, нужны real данные |
| Export | 🚧 | Alert-заглушка, нужна реализация |
| Audit Log | 🆕 | В очереди (Волна 3) |
| Asset History | 🆕 | В очереди (Волна 2) |

---

## 🎬 Что делать дальше? (приоритет)

**Волна 1 (критичные, 1–2 часа):**
1. Экспорт CSV/XLSX вместо alert
2. Отполировать тёмную тему (аудит хардкод-цветов)
3. Пагинация UI для users/notes (backend готов)

**Волна 2 (2–3 часа):**
4. История активов (новая коллекция)
5. Снапшоты метрик (для трендов на дашборде)

**Волна 3 (2–3 часа):**
6. Аудит-лог (логирование всех операций)

Детали: смотри **DEVELOPMENT_QUEUE.md**.

---

## 🔗 Главные ссылки в коде

```
🔐 AUTH:
  backend/routers/auth.py                  (login, logout, refresh, me)
  backend/core/security.py                 (JWT, get_current_user)
  frontend/pages/auth.js                   (форма логина)

👥 USER MANAGEMENT:
  backend/routers/users.py                 (CRUD users, email-инвайт)
  backend/models/user.py                   (User, Permissions model)
  frontend/pages/users.js                  (таблица юзеров)

✅ TASKS (ГОТОВО):
  backend/routers/tasks.py                 (CRUD tasks, полная логика прав)
  backend/models/task.py                   (Task model, convert_doc фикс ObjectId)
  frontend/src/pages/tasks.js              (таблица + фильтры)
  frontend/src/components/task-modal.js    (CRUD форма, 3 режима)

🎨 UI & STATE:
  frontend/src/state.js                    (AppState, can(), isAdmin())
  frontend/src/components/Header.js        (навигация, тема)
  frontend/src/components/Sidebar.js       (меню по правам)
  frontend/src/styles/themes.css           (CSS переменные для темы)

📡 API CLIENT:
  frontend/src/api/client.js               (fetch wrapper, 401 retry)
```

---

## 💬 Задания для новой сессии

Когда ты понял контекст, типичные задания:

1. **"Реализуй [фичу из DEVELOPMENT_QUEUE]"**
   - Прочти описание в DEVELOPMENT_QUEUE.md
   - Посмотри в ARCHITECTURE.md зависимости
   - Реализуй backend → frontend
   - Тестируй

2. **"Что-то не работает в Tasks"**
   - Смотри `backend/routers/tasks.py` и `frontend/src/pages/tasks.js`
   - Проверь `convert_doc()` в tasks.py (ObjectId сериализация)
   - Проверь права в `update_task()` (admin vs user логика)

3. **"Как добавить новое поле в [сущность]"**
   - Обнови модель в `backend/models/[entity].py`
   - Миграция БД (если нужна)
   - Обнови роут (если нужна валидация)
   - Обнови фронт (форма, таблица)

---

## 📞 Важные числа

```
Backend:        localhost:8000
Frontend:       localhost:3000
MongoDB:        localhost:27017
Task page:      http://localhost:3000/#/tasks  (✅ работает)
```

---

## ✅ Чек-лист: перед началом работы убедись

- [ ] Прочитал PROJECT_OVERVIEW.md
- [ ] Знаю где находятся backend/frontend структуры
- [ ] Знаю 6 критичных подводных камней (trailing slash, cookies, ObjectId, и т.д.)
- [ ] Знаю статус каждого блока (что готово, что в очереди)
- [ ] Знаю приоритет Волн 1–6 разработки
- [ ] Может запустить проект локально

**Готов?** → Читай ARCHITECTURE.md (если нужны детали) или DEVELOPMENT_QUEUE.md (если знаешь что делать).
