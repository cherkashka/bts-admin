from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from datetime import datetime

from backend.core.security import get_current_user
from backend.core.database import get_db
from backend.core.permissions import is_admin
from backend.core.audit import log_action, snapshot, diff_changes
from backend.models.category import CategoryCreate, CategoryUpdate, CategoryResponse
from backend.models.user import UserResponse

router = APIRouter(prefix="/api/v1/categories", tags=["categories"], redirect_slashes=False)


def convert_doc(doc):
    """Конвертирует MongoDB-документ для CategoryResponse.

    `_id` (ObjectId) → `id` (str), чтобы JSON-ответ возвращал поле `id`
    (как у assets/users/tasks). Раньше оставляли `_id`, из-за чего
    фронт получал документ с `_id`, а везде ожидался `id`.
    """
    if doc is None:
        return None
    safe = dict(doc)
    safe["id"] = str(safe.pop("_id"))
    return safe


@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: CategoryCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Создать новую категорию для текущего пользователя."""
    # Проверка: не создавать дубликат имени для этого пользователя
    existing = await db.categories.find_one({
        "name": category.name,
        "owner_id": current_user["id"]
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Категория '{category.name}' уже существует"
        )
    
    now = datetime.utcnow()
    category_data = category.model_dump()
    category_data.update({
        "owner_id": current_user["id"],
        "created_at": now,
        "updated_at": now
    })
    
    result = await db.categories.insert_one(category_data)
    created = await db.categories.find_one({"_id": result.inserted_id})

    await log_action(
        db, actor=current_user, action="create", entity_type="category",
        entity_id=result.inserted_id, entity_label=created.get("name", ""),
        after=snapshot(created),
    )

    return CategoryResponse.model_validate(convert_doc(created))


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    include_system: bool = True,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Получить все категории: системные + личные пользователя."""
    query = {"$or": []}
    
    # Всегда включать системные категории (owner_id = None)
    if include_system:
        query["$or"].append({"owner_id": None})
    
    # Включить личные категории пользователя
    query["$or"].append({"owner_id": current_user["id"]})
    
    categories = await db.categories.find(query).sort([("is_default", -1), ("name", 1)]).to_list(length=None)
    
    return [CategoryResponse.model_validate(convert_doc(cat)) for cat in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Получить категорию по ID."""
    from bson import ObjectId
    
    try:
        obj_id = ObjectId(category_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный ID категории"
        )
    
    category = await db.categories.find_one({"_id": obj_id})
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Проверка прав: системная категория или принадлежит пользователю.
    # Admin видит любые категории, в т.ч. чужие — для управления системой.
    if (
        category.get("owner_id") is not None
        and category["owner_id"] != current_user["id"]
        and not is_admin(current_user)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )
    
    return CategoryResponse.model_validate(convert_doc(category))


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    category_update: CategoryUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Обновить категорию."""
    from bson import ObjectId
    
    try:
        obj_id = ObjectId(category_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный ID категории"
        )
    
    # Найти категорию
    category = await db.categories.find_one({"_id": obj_id})
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Проверка прав: нельзя редактировать системные категории (is_default).
    # Это абсолютная защита — даже admin не может ломать системные пресеты.
    if category.get("is_default"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Системные категории нельзя редактировать"
        )

    # Проверка владения: автор или admin
    if category.get("owner_id") != current_user["id"] and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )

    # Проверка на дубликат имени (если имя меняется)
    if category_update.name and category_update.name != category["name"]:
        existing = await db.categories.find_one({
            "name": category_update.name,
            "owner_id": current_user["id"],
            "_id": {"$ne": obj_id}  # Исключить текущую категорию
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Категория '{category_update.name}' уже существует"
            )
    
    # Обновление
    update_data = category_update.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    await db.categories.update_one({"_id": obj_id}, {"$set": update_data})

    updated = await db.categories.find_one({"_id": obj_id})

    before, after = diff_changes(category, update_data)
    if after:
        await log_action(
            db, actor=current_user, action="update", entity_type="category",
            entity_id=obj_id, entity_label=updated.get("name", ""),
            before=before, after=after,
        )
    return CategoryResponse.model_validate(convert_doc(updated))


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user)
):
    """Удалить категорию."""
    from bson import ObjectId
    
    try:
        obj_id = ObjectId(category_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректный ID категории"
        )
    
    category = await db.categories.find_one({"_id": obj_id})
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )
    
    # Нельзя удалять системные категории (даже admin'у)
    if category.get("is_default"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Системные категории нельзя удалять"
        )

    # Удалить может автор или admin
    if category.get("owner_id") != current_user["id"] and not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещён"
        )

    # Проверка: есть ли записи, привязанные к этой категории
    notes_count = await db.notes.count_documents({"category_id": obj_id})
    if notes_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Нельзя удалить категорию: к ней привязано {notes_count} записей"
        )
    
    await db.categories.delete_one({"_id": obj_id})

    await log_action(
        db, actor=current_user, action="delete", entity_type="category",
        entity_id=obj_id, entity_label=category.get("name", ""),
        before=snapshot(category),
    )
    return None
