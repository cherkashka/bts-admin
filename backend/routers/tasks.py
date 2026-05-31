from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.core.database import get_db
from backend.models.task import TaskCreate, TaskUpdate, TaskResponse
from backend.core.security import get_current_user
from backend.core.permissions import require_admin, is_admin
from backend.core.audit import log_action, snapshot, diff_changes
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pymongo.errors import DuplicateKeyError
import logging

logger = logging.getLogger("it_admin_backend")

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["Tasks"],
    redirect_slashes=False
)


def convert_doc(doc: Dict[str, Any]) -> TaskResponse:
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)

    if "description" in doc and not isinstance(doc["description"], str):
        doc["description"] = None

    # Дефолты для старых записей в БД, созданных до добавления полей в модель
    doc.setdefault("start_date", None)
    doc.setdefault("priority", "medium")
    doc.setdefault("status", "pending")
    doc.setdefault("task_type", "user")

    # У TaskResponse model_config: extra="allow" — все поля документа попадают в ответ.
    # Pydantic не умеет сериализовать ObjectId → приводим все ObjectId к строкам.
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)

    return TaskResponse(**doc)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(require_admin),  # ← задачи раздаёт только admin
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    # exclude_none=True: None-поля не сохраняем в MongoDB —
    # пусть поля просто отсутствуют в документе вместо {field: null}
    task_dict = task.model_dump(exclude_none=True)

    # Если указана задача, назначенная пользователю — проверяем, что пользователь существует и активен
    if task_dict.get("assigned_to"):
        if not ObjectId.is_valid(task_dict["assigned_to"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        assigned_user = await db.users.find_one({
            "_id": ObjectId(task_dict["assigned_to"]),
            "is_active": True
        })
        if not assigned_user:
            raise HTTPException(400, "Назначаемый пользователь не найден или неактивен")

        # Денормализация: сохраняем ФИО прямо в документ задачи.
        task_dict["assigned_to_name"] = assigned_user["full_name"]

    # Если указана задача, связанная с активом — проверяем, что актив существует
    if task_dict.get("related_asset_id"):
        if not ObjectId.is_valid(task_dict["related_asset_id"]):
            raise HTTPException(400, "Неверный формат ID актива")

        asset = await db.assets.find_one({"_id": ObjectId(task_dict["related_asset_id"])})
        if not asset:
            raise HTTPException(400, "Связанный актив не найден")

    # Если указана задача, связанная с пользователем — проверяем, что пользователь существует
    if task_dict.get("related_user_id"):
        if not ObjectId.is_valid(task_dict["related_user_id"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        user = await db.users.find_one({"_id": ObjectId(task_dict["related_user_id"])})
        if not user:
            raise HTTPException(400, "Связанный пользователь не найден")

    # Аудит-поля: кто и когда создал
    task_dict["created_by"] = current_user["id"]
    task_dict["updated_by"] = current_user["id"]
    task_dict["created_at"] = datetime.now(timezone.utc)
    task_dict["updated_at"] = datetime.now(timezone.utc)

    try:
        result = await db.tasks.insert_one(task_dict)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Задача с такими параметрами уже существует"
        )

    # Читаем сохранённый документ обратно, чтобы вернуть его с _id → id
    created_doc = await db.tasks.find_one({"_id": result.inserted_id})
    if not created_doc:
        raise HTTPException(500, "Failed to retrieve created task")

    await log_action(
        db, actor=current_user, action="create", entity_type="task",
        entity_id=result.inserted_id, entity_label=created_doc.get("title", ""),
        after=snapshot(created_doc),
    )
    return convert_doc(created_doc)


# Поля, по которым разрешена сортировка (защита от инъекций).
_ALLOWED_SORT_FIELDS = {
    "title", "status", "priority", "task_type",
    "assigned_to_name", "start_date", "due_date", "created_at",
}


@router.get("", response_model=List[TaskResponse])
async def get_tasks(
    response: Response,
    task_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    start_date_gte: Optional[datetime] = None,
    due_date_lte: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 0,
    sort_by: str = "start_date",
    sort_order: str = "asc",
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    query = {}

    # Фильтр по типу задачи (user/admin)
    if task_type:
        query["task_type"] = task_type

    # Фильтр по назначенному пользователю
    if assigned_to:
        query["assigned_to"] = assigned_to

    # Фильтр по дате начала
    if start_date_gte:
        query["start_date"] = {"$gte": start_date_gte}

    # Фильтр по дате окончания
    if due_date_lte:
        query.setdefault("due_date", {})["$lte"] = due_date_lte

    total = await db.tasks.count_documents(query)
    response.headers["X-Total-Count"] = str(total)

    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "start_date"
    direction = -1 if sort_order == "desc" else 1

    cursor = db.tasks.find(query).sort(sort_field, direction)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    # async for — обязателен с Motor: курсор асинхронный
    return [convert_doc(doc) async for doc in cursor if doc]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(400, "Неверный формат ID задачи")

    task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not task:
        raise HTTPException(404, "Задача не найдена")

    return convert_doc(task)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    update_data: TaskUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(400, "Неверный формат ID задачи")

    # Проверяем, существует ли задача
    existing_task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not existing_task:
        raise HTTPException(404, "Задача не найдена")

    # Подготовим данные для обновления
    update_dict = update_data.model_dump(exclude_unset=True)

    # Политика доступа:
    #   admin — может менять всё;
    #   user  — только status у задачи, которая назначена именно ему.
    # Это позволяет исполнителю отметить «взял в работу» / «сделал», но
    # не даёт ему перевешивать задачу на другого или менять сроки.
    if not is_admin(current_user):
        assigned_to = existing_task.get("assigned_to")
        if not assigned_to or str(assigned_to) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно редактировать только задачи, назначенные вам",
            )
        ALLOWED_FIELDS_FOR_USER = {"status"}
        forbidden = set(update_dict.keys()) - ALLOWED_FIELDS_FOR_USER
        if forbidden:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Исполнитель может менять только статус задачи. "
                    f"Запрещённые поля: {', '.join(sorted(forbidden))}"
                ),
            )

    # Обработка назначения задачи пользователю
    if "assigned_to" in update_dict and update_dict["assigned_to"]:
        if not ObjectId.is_valid(update_dict["assigned_to"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        assigned_user = await db.users.find_one({
            "_id": ObjectId(update_dict["assigned_to"]),
            "is_active": True
        })
        if not assigned_user:
            raise HTTPException(400, "Назначаемый пользователь не найден или неактивен")

        # Денормализация: сохраняем ФИО прямо в документ задачи.
        update_dict["assigned_to_name"] = assigned_user["full_name"]
    elif "assigned_to" in update_dict and update_dict["assigned_to"] is None:
        # Исполнитель снят — обнуляем денормализованное имя.
        update_dict["assigned_to_name"] = None

    # Обработка связи с активом
    if "related_asset_id" in update_dict and update_dict["related_asset_id"]:
        if not ObjectId.is_valid(update_dict["related_asset_id"]):
            raise HTTPException(400, "Неверный формат ID актива")

        asset = await db.assets.find_one({"_id": ObjectId(update_dict["related_asset_id"])})
        if not asset:
            raise HTTPException(400, "Связанный актив не найден")

    # Обработка связи с пользователем
    if "related_user_id" in update_dict and update_dict["related_user_id"]:
        if not ObjectId.is_valid(update_dict["related_user_id"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        user = await db.users.find_one({"_id": ObjectId(update_dict["related_user_id"])})
        if not user:
            raise HTTPException(400, "Связанный пользователь не найден")

    # Обновим время последнего изменения
    update_dict["updated_at"] = datetime.now(timezone.utc)
    update_dict["updated_by"] = current_user["id"]

    # Обновляем документ
    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_dict})

    # Получаем обновлённый документ
    updated_task = await db.tasks.find_one({"_id": ObjectId(task_id)})

    before, after = diff_changes(existing_task, update_dict)
    if after:
        await log_action(
            db, actor=current_user, action="update", entity_type="task",
            entity_id=task_id, entity_label=updated_task.get("title", ""),
            before=before, after=after,
        )
    return convert_doc(updated_task)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    current_user: dict = Depends(require_admin),  # ← удаляет задачи только admin
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(task_id):
        raise HTTPException(400, "Неверный формат ID задачи")

    doc = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not doc:
        raise HTTPException(404, "Задача не найдена")

    result = await db.tasks.delete_one({"_id": ObjectId(task_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Задача не найдена")

    await log_action(
        db, actor=current_user, action="delete", entity_type="task",
        entity_id=task_id, entity_label=doc.get("title", ""),
        before=snapshot(doc),
    )
    # При status_code=204 FastAPI не ждёт return — тело ответа пустое