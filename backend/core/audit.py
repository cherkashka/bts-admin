"""
Единый аудит-лог: одна коллекция `audit_log` фиксирует все изменения
сущностей (активы, пользователи, задачи, заметки, категории).

И «История актива», и страница «Аудит-лог» читают из ЭТОЙ коллекции —
единый источник правды по действиям в системе. История конкретного
актива — это просто выборка `entity_type=asset, entity_id=<id>`.

Структура записи:
  - timestamp    — когда (UTC)
  - actor_id     — кто (id пользователя) либо None для системных операций
  - actor_name   — денормализованное имя (username) либо "Система"
  - action       — create | update | delete
  - entity_type  — asset | user | task | note | category
  - entity_id    — id затронутого документа (str)
  - entity_label — человекочитаемая подпись (имя/заголовок/инв. номер)
  - before/after — изменения:
        create → before=None,            after=снимок документа;
        update → before/after только по изменённым полям;
        delete → before=полная копия,    after=None.

Значения внутри before/after хранятся уже в JSON-безопасном виде
(ObjectId → str, datetime → ISO), чтобы чтение лога было тривиальным.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

logger = logging.getLogger("it_admin_backend")

SYSTEM_ACTOR_NAME = "Система"

# Служебные/шумные поля — не показываем в diff и снимках.
_NOISE_FIELDS = {
    "updated_at", "updated_by", "created_at", "created_by", "hashed_password",
}


def _jsonify(value: Any) -> Any:
    """Рекурсивно приводит значение к JSON-безопасному виду:
    ObjectId → str, datetime → ISO-строка. `hashed_password` вырезаем."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items() if k != "hashed_password"}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    return value


def snapshot(doc: Optional[dict]) -> Optional[dict]:
    """Полный JSON-безопасный снимок документа (для create/delete).
    `_id` убираем — он дублируется в `entity_id`."""
    if not doc:
        return None
    clean = {k: v for k, v in doc.items() if k not in ("_id", "hashed_password")}
    return _jsonify(clean)


def diff_changes(old: dict, update: dict) -> tuple[dict, dict]:
    """Сравнивает старый документ и патч (`update_dict`).
    Возвращает (before, after) только по реально изменившимся полям."""
    before: dict = {}
    after: dict = {}
    for key, new_val in update.items():
        if key in _NOISE_FIELDS:
            continue
        old_val = old.get(key)
        if old_val != new_val:
            before[key] = _jsonify(old_val)
            after[key] = _jsonify(new_val)
    return before, after


async def log_action(
    db,
    *,
    actor: Optional[dict],
    action: str,
    entity_type: str,
    entity_id: Any,
    entity_label: str = "",
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> None:
    """Пишет запись в `audit_log`.

    Никогда не роняет основную операцию — любые ошибки записи лога
    глушим в warning (лог не должен блокировать бизнес-действие).

    `actor=None` → системная операция (actor_name="Система").
    """
    try:
        entry = {
            "timestamp":    datetime.now(timezone.utc),
            "actor_id":     (actor.get("id") if actor else None),
            "actor_name":   (actor.get("username") if actor else SYSTEM_ACTOR_NAME),
            "action":       action,
            "entity_type":  entity_type,
            "entity_id":    str(entity_id),
            "entity_label": entity_label or "",
            "before":       before,
            "after":        after,
        }
        await db.audit_log.insert_one(entry)
    except Exception as e:  # noqa: BLE001 — намеренно глушим, см. docstring
        logger.warning(f"⚠️ audit_log write failed ({entity_type}/{action}): {e}")
