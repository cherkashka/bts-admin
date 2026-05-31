"""Pydantic-модель ответа аудит-лога.

Запись создаётся через `backend.core.audit.log_action` (там же — структура).
Здесь только схема чтения для эндпоинта `GET /api/v1/audit`.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_id: Optional[str] = None
    actor_name: str
    action: str            # create | update | delete
    entity_type: str       # asset | user | task | note | category
    entity_id: str
    entity_label: str = ""
    before: Optional[dict] = None
    after: Optional[dict] = None
