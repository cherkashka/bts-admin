from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    actor_id: Optional[str] = None
    actor_name: str
    action: str
    entity_type: str
    entity_id: str
    entity_label: str = ""
    before: Optional[dict] = None
    after: Optional[dict] = None
