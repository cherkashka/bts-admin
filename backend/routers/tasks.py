import re
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from backend.core.database import get_db
from backend.models.task import TaskCreate, TaskUpdate, TaskResponse
from backend.core.security import get_current_user
from backend.core.permissions import require_admin, is_admin, require_permission, has_permission
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

    doc.setdefault("start_date", None)
    doc.setdefault("priority", "medium")
    doc.setdefault("status", "pending")
    doc.setdefault("task_type", "user")

    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)

    return TaskResponse(**doc)

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    current_user: dict = Depends(require_permission("tasks", "create")),
    db: AsyncIOMotorDatabase = Depends(get_db)
):

    task_dict = task.model_dump(exclude_none=True)

    if task_dict.get("assigned_to"):
        if not ObjectId.is_valid(task_dict["assigned_to"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        assigned_user = await db.users.find_one({
            "_id": ObjectId(task_dict["assigned_to"]),
            "is_active": True
        })
        if not assigned_user:
            raise HTTPException(400, "Назначаемый пользователь не найден или неактивен")

        task_dict["assigned_to_name"] = assigned_user["full_name"]

    if task_dict.get("related_asset_id"):
        if not ObjectId.is_valid(task_dict["related_asset_id"]):
            raise HTTPException(400, "Неверный формат ID актива")

        asset = await db.assets.find_one({"_id": ObjectId(task_dict["related_asset_id"])})
        if not asset:
            raise HTTPException(400, "Связанный актив не найден")

    if task_dict.get("related_user_id"):
        if not ObjectId.is_valid(task_dict["related_user_id"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        user = await db.users.find_one({"_id": ObjectId(task_dict["related_user_id"])})
        if not user:
            raise HTTPException(400, "Связанный пользователь не найден")

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

    created_doc = await db.tasks.find_one({"_id": result.inserted_id})
    if not created_doc:
        raise HTTPException(500, "Failed to retrieve created task")

    await log_action(
        db, actor=current_user, action="create", entity_type="task",
        entity_id=result.inserted_id, entity_label=created_doc.get("title", ""),
        after=snapshot(created_doc),
    )
    return convert_doc(created_doc)

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
    search: Optional[str] = None,
    task_status: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    overdue: bool = False,
    skip: int = 0,
    limit: int = 0,
    sort_by: str = "start_date",
    sort_order: str = "asc",
    current_user: dict = Depends(require_permission("tasks", "read")),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    query = {}

    if task_type:
        query["task_type"] = task_type

    if assigned_to:
        query["assigned_to"] = assigned_to

    if start_date_gte:
        query["start_date"] = {"$gte": start_date_gte}

    if due_date_lte:
        query.setdefault("due_date", {})["$lte"] = due_date_lte

    if task_status:
        query["status"] = task_status

    if priority:
        query["priority"] = priority

    if overdue:
        query.setdefault("due_date", {})["$lt"] = datetime.now(timezone.utc)
        if not task_status:
            query["status"] = {"$nin": ["completed", "cancelled"]}

    if search and search.strip():
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"description": rx}, {"assigned_to_name": rx}]

    total = await db.tasks.count_documents(query)
    response.headers["X-Total-Count"] = str(total)

    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "start_date"
    direction = -1 if sort_order == "desc" else 1

    cursor = db.tasks.find(query).sort(sort_field, direction)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)

    return [convert_doc(doc) async for doc in cursor if doc]

@router.get("/stats")
async def get_task_stats(
    current_user: dict = Depends(require_permission("tasks", "read")),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    return {
        "total":       await db.tasks.count_documents({}),
        "in_progress": await db.tasks.count_documents({"status": "in_progress"}),
        "completed":   await db.tasks.count_documents({"status": "completed"}),
        "critical":    await db.tasks.count_documents({
            "priority": "critical",
            "status": {"$nin": ["completed", "cancelled"]},
        }),
    }

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

    if not await has_permission(db, current_user, "tasks", "read"):
        assigned_to = task.get("assigned_to")
        if not assigned_to or str(assigned_to) != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав: read для tasks",
            )

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

    existing_task = await db.tasks.find_one({"_id": ObjectId(task_id)})
    if not existing_task:
        raise HTTPException(404, "Задача не найдена")

    update_dict = update_data.model_dump(exclude_unset=True)

    if not await has_permission(db, current_user, "tasks", "update"):
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

    if "assigned_to" in update_dict and update_dict["assigned_to"]:
        if not ObjectId.is_valid(update_dict["assigned_to"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        assigned_user = await db.users.find_one({
            "_id": ObjectId(update_dict["assigned_to"]),
            "is_active": True
        })
        if not assigned_user:
            raise HTTPException(400, "Назначаемый пользователь не найден или неактивен")

        update_dict["assigned_to_name"] = assigned_user["full_name"]
    elif "assigned_to" in update_dict and update_dict["assigned_to"] is None:

        update_dict["assigned_to_name"] = None

    if "related_asset_id" in update_dict and update_dict["related_asset_id"]:
        if not ObjectId.is_valid(update_dict["related_asset_id"]):
            raise HTTPException(400, "Неверный формат ID актива")

        asset = await db.assets.find_one({"_id": ObjectId(update_dict["related_asset_id"])})
        if not asset:
            raise HTTPException(400, "Связанный актив не найден")

    if "related_user_id" in update_dict and update_dict["related_user_id"]:
        if not ObjectId.is_valid(update_dict["related_user_id"]):
            raise HTTPException(400, "Неверный формат ID пользователя")

        user = await db.users.find_one({"_id": ObjectId(update_dict["related_user_id"])})
        if not user:
            raise HTTPException(400, "Связанный пользователь не найден")

    update_dict["updated_at"] = datetime.now(timezone.utc)
    update_dict["updated_by"] = current_user["id"]

    await db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": update_dict})

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
    current_user: dict = Depends(require_permission("tasks", "delete")),
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
