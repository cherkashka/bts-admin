"""
Роутер для работы с записями календаря (notes).
Записи = пользовательские события в календаре.

Доступ:
- Создание: любой авторизованный пользователь (запись становится его)
- Просмотр (list/one): свои записи + admin видит все
- Редактирование: автор или admin
- Удаление: автор или admin
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from bson import ObjectId
from datetime import datetime
from typing import List

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.core.permissions import is_admin
from backend.core.audit import log_action, snapshot, diff_changes
from backend.models.note import NoteCreate, NoteUpdate, NoteResponse
from backend.models.user import UserResponse

router = APIRouter(prefix="/api/v1/notes", tags=["notes"], redirect_slashes=False)


def validate_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    """Проверка валидности ObjectId."""
    if not ObjectId.is_valid(id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}"
        )
    return ObjectId(id_str)


async def validate_asset_exists(asset_id: str, db) -> None:
    """Проверка существования актива."""
    if asset_id:
        obj_id = validate_object_id(asset_id, "asset_id")
        asset = await db.assets.find_one({"_id": obj_id})
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related asset not found"
            )


async def validate_user_exists(user_id: str, db) -> None:
    """Проверка существования пользователя."""
    if user_id:
        obj_id = validate_object_id(user_id, "user_id")
        user = await db.users.find_one({"_id": obj_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Related user not found"
            )


async def validate_category_exists(category_id: str, db) -> None:
    """Проверка существования категории."""
    if category_id:
        obj_id = validate_object_id(category_id, "category_id")
        category = await db.categories.find_one({"_id": obj_id})
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )


@router.post("/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note: NoteCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Создать новую запись.
    
    Доступ: любой авторизованный пользователь
    created_by автоматически устанавливается = текущий пользователь
    """
    # Валидация связанных сущностей
    await validate_asset_exists(note.related_asset_id, db)
    await validate_user_exists(note.related_user_id, db)
    if note.category_id:
        await validate_category_exists(note.category_id, db)
    
    # Подготовка данных для БД
    note_data = note.model_dump()
    
    # Автоматически устанавливаем создателя (неизменяемо)
    note_data["created_by"] = ObjectId(current_user.get("id"))
    
    # Конвертируем строки в ObjectId для внешних ссылок (но не category_id — он может быть None)
    if note_data.get("related_asset_id"):
        note_data["related_asset_id"] = ObjectId(note_data["related_asset_id"])
    if note_data.get("related_user_id"):
        note_data["related_user_id"] = ObjectId(note_data["related_user_id"])
    if note_data.get("category_id"):
        note_data["category_id"] = ObjectId(note_data["category_id"])
    
    # Временные метки
    note_data["created_at"] = datetime.utcnow()
    note_data["updated_at"] = datetime.utcnow()
    
    # Сохранение в БД
    result = await db.notes.insert_one(note_data)
    note_data["_id"] = result.inserted_id

    await log_action(
        db, actor=current_user, action="create", entity_type="note",
        entity_id=result.inserted_id, entity_label=note_data.get("title", ""),
        after=snapshot(note_data),
    )
    
    # Конвертируем ObjectId в строки для ответа + добавляем цвет из категории для обратной совместимости
    response_data = note_data.copy()
    response_data["id"] = str(response_data.pop("_id"))
    response_data["created_by"] = str(response_data["created_by"])
    if response_data.get("related_asset_id"):
        response_data["related_asset_id"] = str(response_data["related_asset_id"])
    if response_data.get("related_user_id"):
        response_data["related_user_id"] = str(response_data["related_user_id"])
    if response_data.get("category_id"):
        response_data["category_id"] = str(response_data["category_id"])
    
    return NoteResponse(**response_data)


# Поля, по которым разрешена сортировка (защита от инъекций).
_ALLOWED_SORT_FIELDS = {"title", "event_start", "event_end", "created_at", "updated_at"}


@router.get("/", response_model=List[NoteResponse])
async def get_notes(
    response: Response,
    skip: int = 0,
    limit: int = 0,            # 0 = все
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Получить записи.

    - admin видит все записи в системе;
    - user видит только свои (по `created_by`).
    """
    query = {} if is_admin(current_user) else {"created_by": ObjectId(current_user["id"])}
    total = await db.notes.count_documents(query)
    response.headers["X-Total-Count"] = str(total)

    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "created_at"
    direction = -1 if sort_order == "desc" else 1

    cursor = db.notes.find(query).sort(sort_field, direction)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    notes = await cursor.to_list(length=None)
    
    # Конвертируем ObjectId в строки
    result = []
    for note in notes:
        note_data = note.copy()
        note_data["id"] = str(note_data.pop("_id"))
        note_data["created_by"] = str(note_data["created_by"])
        if note_data.get("related_asset_id"):
            note_data["related_asset_id"] = str(note_data["related_asset_id"])
        if note_data.get("related_user_id"):
            note_data["related_user_id"] = str(note_data["related_user_id"])
        if note_data.get("category_id"):
            note_data["category_id"] = str(note_data["category_id"])
        result.append(note_data)
    
    return result


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    db=Depends(get_db),  # ← ИСПРАВЛЕНО
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Получить одну запись по ID.
    
    Доступ: любой авторизованный пользователь
    """
    obj_id = validate_object_id(note_id, "note_id")
    note = await db.notes.find_one({"_id": obj_id})

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Доступ к чужой записи — только админу
    if not is_admin(current_user) and str(note.get("created_by")) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к чужой записи запрещён"
        )

    # Конвертируем ObjectId в строки
    note["id"] = str(note.pop("_id"))
    note["created_by"] = str(note["created_by"])
    if note.get("related_asset_id"):
        note["related_asset_id"] = str(note["related_asset_id"])
    if note.get("related_user_id"):
        note["related_user_id"] = str(note["related_user_id"])
    if note.get("category_id"):
        note["category_id"] = str(note["category_id"])

    return NoteResponse(**note)


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    note_update: NoteUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Обновить существующую запись.
    
    Доступ: любой авторизованный пользователь
    created_by НЕ может быть изменён
    """
    obj_id = validate_object_id(note_id, "note_id")

    # Проверка владения: редактировать может только автор или admin
    existing = await db.notes.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    if not is_admin(current_user) and str(existing.get("created_by")) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Редактировать можно только свои записи"
        )

    # Валидация связанных сущностей (только если поле передаётся)
    if note_update.related_asset_id is not None:
        await validate_asset_exists(note_update.related_asset_id, db)
    if note_update.related_user_id is not None:
        await validate_user_exists(note_update.related_user_id, db)
    if note_update.category_id is not None:
        await validate_category_exists(note_update.category_id, db)

    # Подготовка данных для обновления
    update_data = note_update.model_dump(exclude_unset=True)
    
    # ЗАПРЕТ изменения created_by (безопасность)
    if "created_by" in update_data:
        del update_data["created_by"]
    
    # Конвертируем строки в ObjectId для внешних ссылок (но не category_id — он может быть None)
    if update_data.get("related_asset_id"):
        update_data["related_asset_id"] = ObjectId(update_data["related_asset_id"])
    if update_data.get("related_user_id"):
        update_data["related_user_id"] = ObjectId(update_data["related_user_id"])
    if update_data.get("category_id"):
        update_data["category_id"] = ObjectId(update_data["category_id"])
    
    # Обновляем временную метку
    update_data["updated_at"] = datetime.utcnow()
    
    # Обновление в БД
    updated_note = await db.notes.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_data},
        return_document=True
    )
    
    if not updated_note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    before, after = diff_changes(existing, update_data)
    if after:
        await log_action(
            db, actor=current_user, action="update", entity_type="note",
            entity_id=obj_id, entity_label=updated_note.get("title", ""),
            before=before, after=after,
        )

    # Конвертируем ObjectId в строки для ответа + добавляем цвет из категории для обратной совместимости
    updated_note["id"] = str(updated_note.pop("_id"))
    updated_note["created_by"] = str(updated_note["created_by"])
    if updated_note.get("related_asset_id"):
        updated_note["related_asset_id"] = str(updated_note["related_asset_id"])
    if updated_note.get("related_user_id"):
        updated_note["related_user_id"] = str(updated_note["related_user_id"])
    if updated_note.get("category_id"):
        updated_note["category_id"] = str(updated_note["category_id"])
    
    return NoteResponse(**updated_note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: str,
    db=Depends(get_db),  # ← ИСПРАВЛЕНО
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Удалить запись.
    
    Доступ: любой авторизованный пользователь
    """
    obj_id = validate_object_id(note_id, "note_id")

    # Проверка владения: удалить может только автор или admin
    existing = await db.notes.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    if not is_admin(current_user) and str(existing.get("created_by")) != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Удалять можно только свои записи"
        )

    await db.notes.delete_one({"_id": obj_id})

    await log_action(
        db, actor=current_user, action="delete", entity_type="note",
        entity_id=obj_id, entity_label=existing.get("title", ""),
        before=snapshot(existing),
    )

    # Возвращаем 204 No Content
    return None