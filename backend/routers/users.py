import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Optional

from backend.core.database import get_db
from backend.core.security import get_current_user, get_password_hash
from backend.core.permissions import require_admin
from backend.core.audit import log_action, snapshot, diff_changes
from backend.core.transliterate import unique_username
from backend.core.mailer import send_email, build_invite_html, build_invite_text
from backend.core.config import settings
from backend.models.user import UserInviteCreate, UserUpdate, UserSelfUpdate, UserResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"], redirect_slashes=False)

_ALPHA = string.ascii_letters + string.digits


def _gen_password(length: int = 12) -> str:
    return ''.join(secrets.choice(_ALPHA) for _ in range(length))


async def _active_admin_count(db: AsyncIOMotorDatabase) -> int:
    """Число активных администраторов — для защиты от потери доступа к системе."""
    return await db.users.count_documents({"role": "admin", "is_active": True})


def _serialize_user(user: dict) -> UserResponse:
    user["id"] = str(user["_id"])
    user.pop("_id", None)
    user.pop("hashed_password", None)
    user.setdefault("is_active", True)
    user.setdefault("is_activated", True)
    user.setdefault("password_change_required", False)
    user.setdefault("phone", None)
    user.setdefault("created_at", None)
    user.setdefault("permissions", {
        "assets":     {"create": False, "read": False, "update": False, "delete": False},
        "tasks":      {"create": False, "read": False, "update": False, "delete": False},
        "notes":      {"create": False, "read": False, "update": False, "delete": False},
        "categories": {"create": False, "read": False, "update": False, "delete": False},
    })
    return UserResponse(**user)


# Поля, по которым разрешена сортировка (защита от инъекций).
_ALLOWED_SORT_FIELDS = {"username", "full_name", "email", "role", "is_active", "created_at"}


@router.get("", response_model=List[UserResponse])
async def get_users(
    response: Response,
    active_only: Optional[bool] = None,
    skip: int = 0,
    limit: int = 0,            # 0 = все
    sort_by: str = "full_name",
    sort_order: str = "asc",
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = {}
    if active_only is True:  query["is_active"] = True
    if active_only is False: query["is_active"] = False

    total = await db.users.count_documents(query)
    response.headers["X-Total-Count"] = str(total)

    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "full_name"
    direction = -1 if sort_order == "desc" else 1

    cursor = db.users.find(query).sort(sort_field, direction)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    users = await cursor.to_list(length=None)  # без лимита; режется skip/limit выше
    return [_serialize_user(u) for u in users]


@router.post("", status_code=201)
async def create_user(
    user_in: UserInviteCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Создаёт пользователя и отправляет инвайт на email."""
    if await db.users.find_one({"email": user_in.email}):
        raise HTTPException(400, "Email уже зарегистрирован")

    username = await unique_username(user_in.full_name, db)
    password = _gen_password()

    user_data = {
        "username":                username,
        "hashed_password":         get_password_hash(password),
        "full_name":               user_in.full_name,
        "email":                   user_in.email,
        "phone":                   user_in.phone,
        "role":                    "user",
        "is_active":               True,
        "is_activated":            False,
        "password_change_required": True,
        "permissions":             user_in.permissions.model_dump(),
        "created_at":              datetime.now(timezone.utc),
    }

    result = await db.users.insert_one(user_data)
    new_user = await db.users.find_one({"_id": result.inserted_id})

    await log_action(
        db, actor=admin, action="create", entity_type="user",
        entity_id=result.inserted_id, entity_label=new_user.get("full_name", ""),
        after=snapshot(new_user),
    )

    login_url = f"{settings.FRONTEND_URL}/#/login"
    html = build_invite_html(user_in.full_name, username, password, login_url)
    text = build_invite_text(user_in.full_name, username, password, login_url)
    email_sent = await send_email(
        to=user_in.email,
        subject=f"Ваши данные для входа в IT Admin System",
        html_body=html,
        text_body=text,
    )

    return {
        "user":        _serialize_user(new_user),
        "credentials": {"username": username, "password": password},
        "email_sent":  email_sent,
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "Неверный формат ID")
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    return _serialize_user(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_in: UserUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "Неверный формат ID")
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(404, "Пользователь не найден")

    update_data = user_in.model_dump(exclude_unset=True)

    if "permissions" in update_data and update_data["permissions"] is not None:
        update_data["permissions"] = update_data["permissions"]

    if "email" in update_data and update_data["email"]:
        if await db.users.find_one({"email": update_data["email"], "_id": {"$ne": ObjectId(user_id)}}):
            raise HTTPException(400, "Email уже зарегистрирован")

    # Защита: нельзя снять права/деактивировать последнего активного админа.
    removes_admin = (
        update_data.get("role") == "user"
        or update_data.get("is_active") is False
    )
    if (
        removes_admin
        and existing.get("role") == "admin"
        and existing.get("is_active", True)
        and await _active_admin_count(db) <= 1
    ):
        raise HTTPException(400, "Нельзя снять права или деактивировать последнего администратора")

    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": update_data})
    updated = await db.users.find_one({"_id": ObjectId(user_id)})

    before, after = diff_changes(existing, update_data)
    if after:
        await log_action(
            db, actor=admin, action="update", entity_type="user",
            entity_id=user_id, entity_label=updated.get("full_name", ""),
            before=before, after=after,
        )
    return _serialize_user(updated)


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    """Сброс пароля администратором.

    Логика как у первого входа: генерируем новый временный пароль,
    помечаем аккаунт `password_change_required=True` (+ снимаем активацию),
    отправляем письмо с реквизитами. Возвращаем сами реквизиты, чтобы
    админ мог передать их вручную, если письмо не доставлено.
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "Неверный формат ID")
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if not user.get("email"):
        raise HTTPException(400, "У пользователя не указан email — отправить новый пароль некуда")

    new_password = _gen_password()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "hashed_password":          get_password_hash(new_password),
            "password_change_required": True,
            "is_activated":             False,
        }}
    )

    login_url = f"{settings.FRONTEND_URL}/#/login"
    html = build_invite_html(user["full_name"], user["username"], new_password, login_url)
    text = build_invite_text(user["full_name"], user["username"], new_password, login_url)
    email_sent = await send_email(
        to=user["email"],
        subject="Сброс пароля — IT Admin System",
        html_body=html,
        text_body=text,
    )

    await log_action(
        db, actor=admin, action="update", entity_type="user",
        entity_id=user_id, entity_label=user.get("full_name", ""),
        before={"password_change_required": user.get("password_change_required", False)},
        after={"password_change_required": True},
    )

    return {
        "credentials": {"username": user["username"], "password": new_password},
        "email_sent":  email_sent,
    }


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    admin: dict = Depends(require_admin)
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "Неверный формат ID")
    if user_id == admin.get("id"):
        raise HTTPException(400, "Нельзя деактивировать собственный аккаунт")
    existing = await db.users.find_one({"_id": ObjectId(user_id)})
    if not existing:
        raise HTTPException(404, "Пользователь не найден")
    # Не оставляем систему без активного администратора.
    if (
        existing.get("role") == "admin"
        and existing.get("is_active", True)
        and await _active_admin_count(db) <= 1
    ):
        raise HTTPException(400, "Нельзя деактивировать последнего активного администратора")
    result = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_active": False}})
    if result.matched_count == 0:
        raise HTTPException(404, "Пользователь не найден")

    # Деактивация — это мягкое удаление: фиксируем как изменение is_active.
    if existing.get("is_active", True):
        await log_action(
            db, actor=admin, action="update", entity_type="user",
            entity_id=user_id, entity_label=existing.get("full_name", ""),
            before={"is_active": True}, after={"is_active": False},
        )
