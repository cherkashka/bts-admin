"""
Централизованные dependency-проверки прав доступа.

Используем как FastAPI Depends — это даёт единый источник правды
для всех роутов и избавляет от дублирования inline-проверок роли.

Модель ролей: `user` | `admin` (см. backend/models/user.py).
"""
from fastapi import Depends, HTTPException, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.security import get_current_user
from backend.core.database import get_db


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Пропускает только администраторов.

    Используется на роутах CRUD-операций для активов, задач, пользователей
    и других admin-only действий. Возвращает данные текущего пользователя
    (роль уже подтверждена), чтобы их можно было использовать дальше
    в обработчике (например, для аудит-полей `created_by`/`updated_by`).
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Действие доступно только администратору",
        )
    return current_user


def is_admin(current_user: dict) -> bool:
    """Утилита для inline-проверок в роутах со смешанной логикой."""
    return current_user.get("role") == "admin"


def require_permission(resource: str, action: str):
    """
    Фабрика dependency для проверки гранулярных прав.

    Пример: `Depends(require_permission("assets", "create"))`.
    Admin всегда проходит (bypass). User — только если у него есть флаг.
    """
    async def checker(
        current_user: dict = Depends(get_current_user),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        if is_admin(current_user):
            return current_user

        user_doc = await db.users.find_one({"_id": ObjectId(current_user["id"])})
        perms = (user_doc or {}).get("permissions", {})
        resource_perms = perms.get(resource, {}) if isinstance(perms, dict) else {}
        if not resource_perms.get(action, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Нет прав: {action} для {resource}",
            )
        return current_user

    return checker
