from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CategoryBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Название категории (Работа, Встречи, Личное)"
    )
    color: str = Field(
        ...,
        pattern=r'^#[0-9a-fA-F]{6}$',
        description="Hex-код цвета (например, #3b82f6)"
    )
    icon: Optional[str] = Field(
        None,
        max_length=20,
        description="Эмодзи или CSS-класс иконки (опционально)"
    )
    is_default: bool = Field(
        default=False,
        description="Системная категория (не удаляется пользователем)"
    )

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern=r'^#[0-9a-fA-F]{6}$')
    icon: Optional[str] = Field(None, max_length=20)
    is_default: Optional[bool] = None

class CategoryResponse(CategoryBase):
    id: str
    owner_id: Optional[str] = Field(
        None,
        description="ID владельца (None = системная категория, видна всем)"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
