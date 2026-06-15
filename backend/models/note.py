from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime

COLOR_HEX_MAP = {
    "red": "#ef4444",
    "orange": "#f97316",
    "yellow": "#eab308",
    "green": "#22c55e",
    "blue": "#3b82f6",
    "purple": "#a855f7",
    "gray": "#6b7280"
}

class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Заголовок записи")
    content: Optional[str] = Field(None, max_length=2000, description="Описание записи")
    event_start: datetime = Field(..., description="Дата и время начала события")
    event_end: datetime = Field(..., description="Дата и время окончания (для разовых = event_start)")
    category_id: Optional[str] = Field(None, description="ID категории (опционально, по умолчанию — системная)")
    related_asset_id: Optional[str] = Field(None, description="ID связанного актива (опционально)")
    related_user_id: Optional[str] = Field(None, description="ID связанного пользователя (опционально)")

    @model_validator(mode="after")
    def end_not_before_start(self):
        if self.event_end < self.event_start:
            raise ValueError("Окончание события не может быть раньше начала")
        return self

class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, max_length=2000)
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    category_id: Optional[str] = None
    related_asset_id: Optional[str] = None
    related_user_id: Optional[str] = None

class NoteResponse(BaseModel):
    id: str
    title: str
    content: Optional[str] = None
    event_start: datetime
    event_end: datetime
    category_id: Optional[str] = None
    related_asset_id: Optional[str] = None
    related_user_id: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
