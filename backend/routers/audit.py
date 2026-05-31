"""Аудит-лог — чтение журнала действий.

Только admin. Одна коллекция `audit_log` (см. backend/core/audit.py)
питает и страницу `/audit`, и вкладку «История» на странице актива.
История актива — выборка `?entity_type=asset&entity_id=<id>`.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.database import get_db
from backend.core.permissions import require_admin
from backend.models.audit import AuditLogResponse

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"], redirect_slashes=False)

_ENTITY_TYPES = {"asset", "user", "task", "note", "category"}
_ACTIONS = {"create", "update", "delete"}


def _convert(doc: dict) -> AuditLogResponse:
    safe = dict(doc)
    safe["id"] = str(safe.pop("_id"))
    return AuditLogResponse(**safe)


@router.get("", response_model=List[AuditLogResponse])
async def get_audit_log(
    response: Response,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    days: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Журнал действий с фильтрами. Сортировка — всегда от новых к старым.

    - `entity_type` / `entity_id` — конкретная сущность (история актива);
    - `actor_id` — действия одного пользователя;
    - `action` — create/update/delete;
    - `days` — последние N дней;
    - `skip`/`limit` — постранично, `X-Total-Count` в заголовке.
    """
    query: dict = {}
    if entity_type in _ENTITY_TYPES:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    if actor_id:
        query["actor_id"] = actor_id
    if action in _ACTIONS:
        query["action"] = action
    if days and days > 0:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query["timestamp"] = {"$gte": since}

    total = await db.audit_log.count_documents(query)
    response.headers["X-Total-Count"] = str(total)

    cursor = db.audit_log.find(query).sort("timestamp", -1)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    return [_convert(doc) async for doc in cursor]
