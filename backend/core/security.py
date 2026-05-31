from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Cookie
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.config import settings
from backend.core.database import get_db

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta=None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

async def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> dict:
    if not access_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Неверный тип токена")
        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id or not username:
            raise HTTPException(status_code=401, detail="Невалидный токен")
        user = await db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
        if not user:
            raise HTTPException(status_code=401, detail="Пользователь не найден")
        return {"id": str(user["_id"]), "username": username, "role": payload.get("role", "user")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Невалидный или истёкший токен")
