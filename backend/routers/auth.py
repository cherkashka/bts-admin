from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie
from typing import Optional
from jose import jwt, JWTError
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.database import get_db
from backend.models.user import UserLogin, UserSelfUpdate
from backend.core.security import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, get_current_user
)
from backend.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"], redirect_slashes=False)

def _set_tokens(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True,
                        secure=settings.is_production, samesite="lax", max_age=1800, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True,
                        secure=settings.is_production, samesite="lax",
                        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/")

@router.post("/login")
async def login(
    credentials: UserLogin,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    user = await db.users.find_one({"username": credentials.username})
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(401, "Неверный логин или пароль")
    if not user.get("is_active", True):
        raise HTTPException(403, "Аккаунт деактивирован администратором. Обратитесь в поддержку.")

    token_data = {
        "sub":      str(user["_id"]),
        "username": user["username"],
        "role":     user.get("role", "user"),
    }
    _set_tokens(response, create_access_token(token_data), create_refresh_token(token_data))
    return {
        "status":                   "success",
        "username":                 credentials.username,
        "password_change_required": user.get("password_change_required", False),
    }

@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not refresh_token:
        raise HTTPException(401, "Refresh токен отсутствует")
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Неверный тип токена")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"]), "is_active": True})
        if not user:
            raise HTTPException(401, "Пользователь не найден")
        token_data = {"sub": str(user["_id"]), "username": user["username"], "role": user.get("role", "user")}
        _set_tokens(response, create_access_token(token_data), create_refresh_token(token_data))
        return {"status": "success"}
    except JWTError:
        raise HTTPException(401, "Невалидный или истёкший refresh-токен")

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"status": "success"}

@router.get("/me")
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    default_perms = {
        "assets":     {"create": False, "read": False, "update": False, "delete": False},
        "tasks":      {"create": False, "read": False, "update": False, "delete": False},
        "notes":      {"create": False, "read": False, "update": False, "delete": False},
        "categories": {"create": False, "read": False, "update": False, "delete": False},
    }

    return {
        "status": "authenticated",
        "user": {
            "id":                       str(user["_id"]),
            "username":                 user["username"],
            "full_name":                user.get("full_name", ""),
            "email":                    user.get("email"),
            "phone":                    user.get("phone"),
            "role":                     user.get("role", "user"),
            "is_active":                user.get("is_active", True),
            "is_activated":             user.get("is_activated", True),
            "password_change_required": user.get("password_change_required", False),
            "permissions":              user.get("permissions", default_perms),
            "theme":                    user.get("theme"),
        }
    }

@router.patch("/me")
async def update_me(
    data: UserSelfUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    update: dict = {}

    if data.password is not None:
        update["hashed_password"]          = get_password_hash(data.password)
        update["password_change_required"] = False
        update["is_activated"]             = True

    if data.phone is not None:
        update["phone"] = data.phone.strip() or None

    if data.theme is not None:
        update["theme"] = data.theme

    if not update:
        return {"status": "noop"}

    await db.users.update_one({"_id": ObjectId(current_user["id"])}, {"$set": update})
    return {"status": "success"}
