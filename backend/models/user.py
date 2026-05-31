from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from datetime import datetime


class ResourcePermissions(BaseModel):
    create: bool = False
    read:   bool = False
    update: bool = False
    delete: bool = False


class UserPermissions(BaseModel):
    assets:     ResourcePermissions = Field(default_factory=ResourcePermissions)
    tasks:      ResourcePermissions = Field(default_factory=ResourcePermissions)
    notes:      ResourcePermissions = Field(default_factory=ResourcePermissions)
    categories: ResourcePermissions = Field(default_factory=ResourcePermissions)


class UserInviteCreate(BaseModel):
    """Форма, которую заполняет админ при создании нового пользователя."""
    full_name:   str = Field(..., min_length=2, max_length=100)
    email:       str  # обязателен — инвайт отправляется на него
    phone:       Optional[str] = None
    permissions: UserPermissions = Field(default_factory=UserPermissions)

    @field_validator("email", mode="before")
    @classmethod
    def email_must_be_non_empty(cls, v):
        if not v or (isinstance(v, str) and v.strip() == ""):
            raise ValueError("Email обязателен для создания пользователя")
        return v.strip()


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    """Обновление пользователя администратором."""
    full_name:   Optional[str] = None
    email:       Optional[str] = None
    phone:       Optional[str] = None
    role:        Optional[str] = Field(None, pattern=r'^(user|admin)$')
    is_active:   Optional[bool] = None
    permissions: Optional[UserPermissions] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class UserSelfUpdate(BaseModel):
    """Самообслуживание — страница первого входа и /settings.

    Поля опциональны: можно прислать только то, что меняется
    (например, только `theme` после клика по переключателю).
    Если приходит `password` — обязательно `password_confirm` и они
    должны совпадать (валидация ниже).
    """
    phone:            Optional[str] = None
    password:         Optional[str] = Field(None, min_length=8)
    password_confirm: Optional[str] = None
    theme:            Optional[Literal["light", "dark"]] = None

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v, info):
        password = info.data.get("password")
        if password is None:
            # Пароль не меняем — confirm не проверяем.
            return v
        if v is None:
            raise ValueError("Требуется подтверждение пароля")
        if v != password:
            raise ValueError("Пароли не совпадают")
        return v


class UserResponse(BaseModel):
    id:                       str
    username:                 str
    full_name:                str
    email:                    Optional[str] = None
    phone:                    Optional[str] = None
    role:                     str
    is_active:                bool
    is_activated:             bool = True
    password_change_required: bool = False
    permissions:              UserPermissions = Field(default_factory=UserPermissions)
    theme:                    Optional[Literal["light", "dark"]] = None
    created_at:               Optional[datetime] = None
    model_config = {"from_attributes": True}
