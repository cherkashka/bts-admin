from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    start_date: datetime
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    priority: str = Field(default="medium", pattern=r'^(low|medium|high|critical)$')
    status: str = Field(default="pending", pattern=r'^(pending|in_progress|completed|cancelled)$')
    task_type: str = Field(default="admin", pattern=r'^(user|admin)$')
    related_asset_id: Optional[str] = None
    related_user_id: Optional[str] = None

class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    priority: Optional[str] = Field(None, pattern=r'^(low|medium|high|critical)$')
    status: Optional[str] = Field(None, pattern=r'^(pending|in_progress|completed|cancelled)$')
    task_type: Optional[str] = Field(None, pattern=r'^(user|admin)$')
    related_asset_id: Optional[str] = None
    related_user_id: Optional[str] = None

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")
    id: str
    title: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    assigned_to_name: Optional[str] = None
    priority: str = "medium"
    status: str = "pending"
    task_type: str = "user"
    related_asset_id: Optional[str] = None
    related_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
