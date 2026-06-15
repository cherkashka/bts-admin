from fastapi import Depends, HTTPException, status
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.security import get_current_user
from backend.core.database import get_db

async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Действие доступно только администратору",
        )
    return current_user

def is_admin(current_user: dict) -> bool:
    return current_user.get("role") == "admin"

async def has_permission(db: AsyncIOMotorDatabase, current_user: dict,
                         resource: str, action: str) -> bool:
    if is_admin(current_user):
        return True
    user_doc = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    perms = (user_doc or {}).get("permissions", {})
    resource_perms = perms.get(resource, {}) if isinstance(perms, dict) else {}
    return bool(resource_perms.get(action, False))

def require_permission(resource: str, action: str):
    async def checker(
        current_user: dict = Depends(get_current_user),
        db: AsyncIOMotorDatabase = Depends(get_db),
    ) -> dict:
        if not await has_permission(db, current_user, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Нет прав: {action} для {resource}",
            )
        return current_user

    return checker
