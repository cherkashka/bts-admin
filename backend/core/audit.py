import logging
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId

logger = logging.getLogger("it_admin_backend")

SYSTEM_ACTOR_NAME = "Система"

_NOISE_FIELDS = {
    "updated_at", "updated_by", "created_at", "created_by", "hashed_password",
}

def _jsonify(value: Any) -> Any:
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
    if not doc:
        return None
    clean = {k: v for k, v in doc.items() if k not in ("_id", "hashed_password")}
    return _jsonify(clean)

def diff_changes(old: dict, update: dict) -> tuple[dict, dict]:
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
    except Exception as e:
        logger.warning(f"⚠️ audit_log write failed ({entity_type}/{action}): {e}")
