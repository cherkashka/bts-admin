from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.core.permissions import is_admin
from datetime import datetime, date
from typing import List, Dict, Any, Optional

router = APIRouter(
    prefix="/api/v1/calendar",
    tags=["Calendar"],
    redirect_slashes=False
)


def parse_date(value: Optional[str], name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Неверный формат даты {name}")


@router.get("/events", response_model=List[Dict[str, Any]])
async def get_calendar_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
    only_mine: bool = False,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Календарь = задачи + жизненный цикл активов (commission/warranty) + заметки.

    Видимость:
      - admin видит всё (включая инфраструктурные события активов);
      - user видит свои задачи / заметки + системные события активов скрыты;
      - `only_mine=true` (доступно всем) — оставляет только то, что закреплено
        за текущим пользователем (`assigned_to` для задач, `created_by` для
        заметок), активы при этом не показываются.
    """
    start_date = parse_date(start, 'start')
    end_date = parse_date(end, 'end')

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail='Параметры start и end обязательны')

    if start_date > end_date:
        raise HTTPException(status_code=400, detail='Параметр start не может быть позже end')

    events: List[Dict[str, Any]] = []
    user_id = current_user["id"]
    user_is_admin = is_admin(current_user)
    # При only_mine, или для обычного user без admin прав, прячем
    # инфраструктурные события активов (commission/warranty).
    show_assets = user_is_admin and not only_mine
    # Задачи и заметки: user видит свои; при only_mine — все видят только свои.
    restrict_to_self = only_mine or not user_is_admin

    # ===== TASKS =====
    task_query = {
        "$or": [
            {"start_date": {"$gte": datetime.combine(start_date, datetime.min.time())}},
            {"event_start": {"$gte": datetime.combine(start_date, datetime.min.time())}},
            {"due_date": {"$gte": datetime.combine(start_date, datetime.min.time())}},
            {"deadline": {"$gte": datetime.combine(start_date, datetime.min.time())}}
        ],
        "$and": [
            {"$or": [
                {"start_date": {"$lte": datetime.combine(end_date, datetime.max.time())}},
                {"event_start": {"$lte": datetime.combine(end_date, datetime.max.time())}},
                {"due_date": {"$lte": datetime.combine(end_date, datetime.max.time())}},
                {"deadline": {"$lte": datetime.combine(end_date, datetime.max.time())}}
            ]}
        ]
    }
    # Фильтр по принадлежности: только назначенные на текущего пользователя.
    # `assigned_to` хранится как строка с id (см. routers/tasks.py), поэтому
    # сравниваем со строковым current_user["id"], без приведения к ObjectId.
    if restrict_to_self:
        task_query["$and"].append({"assigned_to": user_id})

    cursor = db.tasks.find(task_query)
    async for task in cursor:
        task_id = str(task.get("_id"))
        title = task.get("title", "Задача")
        
        start_value = task.get("start_date") or task.get("event_start")
        if start_value:
            date_value = start_value.date().isoformat()
            events.append({
                "id": f"task-start-{task_id}",
                "source": "task",
                "type": "task_start",
                "title": "Начало задачи: " + title,
                "date": date_value,
                "link": "#/assets",
                "related_id": task_id
            })
        
        due_value = task.get("due_date") or task.get("deadline")
        if due_value:
            date_value = due_value.date().isoformat()
            events.append({
                "id": f"task-due-{task_id}",
                "source": "task",
                "type": "task_due",
                "title": "Дедлайн задачи: " + title,
                "date": date_value,
                "link": "#/assets",
                "related_id": task_id
            })

    # ===== ASSETS =====
    # Активы (commission / warranty_end) — инфраструктурные события.
    # Показываем только админу и только если фильтр "только мои" не активен.
    if show_assets:
        asset_query = {
            "$or": [
                {"commission_date": {"$gte": datetime.combine(start_date, datetime.min.time())}},
                {"warranty_end_date": {"$gte": datetime.combine(start_date, datetime.min.time())}}
            ],
            "$and": [
                {"$or": [
                    {"commission_date": {"$lte": datetime.combine(end_date, datetime.max.time())}},
                    {"warranty_end_date": {"$lte": datetime.combine(end_date, datetime.max.time())}}
                ]}
            ]
        }

        cursor = db.assets.find(asset_query)
        async for asset in cursor:
            asset_id = str(asset.get("_id"))
            name = asset.get("name", "Актив")

            if asset.get("commission_date"):
                date_value = asset["commission_date"].date().isoformat()
                events.append({
                    "id": f"asset-commission-{asset_id}",
                    "source": "asset",
                    "type": "commission",
                    "title": "Ввод в эксплуатацию: " + name,
                    "date": date_value,
                    "link": f"#/assets/edit/{asset_id}",
                    "related_id": asset_id
                })

            if asset.get("warranty_end_date"):
                date_value = asset["warranty_end_date"].date().isoformat()
                events.append({
                    "id": f"asset-warranty-{asset_id}",
                    "source": "asset",
                    "type": "warranty_end",
                    "title": "Окончание гарантии: " + name,
                    "date": date_value,
                    "link": f"#/assets/edit/{asset_id}",
                    "related_id": asset_id
                })

    # ===== NOTES =====
    notes_query = {
        "$or": [
            {
                "event_start": {
                    "$gte": datetime.combine(start_date, datetime.min.time()),
                    "$lte": datetime.combine(end_date, datetime.max.time())
                }
            },
            {
                "event_end": {
                    "$gte": datetime.combine(start_date, datetime.min.time()),
                    "$lte": datetime.combine(end_date, datetime.max.time())
                }
            },
            {
                "event_start": {"$lte": datetime.combine(start_date, datetime.min.time())},
                "event_end": {"$gte": datetime.combine(end_date, datetime.max.time())}
            }
        ]
    }
    # Фильтр приватности заметок: user видит только свои, admin — все.
    # При only_mine — все видят только свои. created_by в notes хранится
    # как ObjectId (см. routers/notes.py), поэтому приводим.
    if restrict_to_self:
        notes_query["created_by"] = ObjectId(user_id)

    cursor = db.notes.find(notes_query)
    async for note in cursor:
        note_id = str(note.get("_id"))
        title = note.get("title", "Запись")
        
        # Получение цвета из связанной категории (или дефолтный)
        color_hex = "#3b82f6"  # дефолтный синий цвет (blue)
        if note.get("category_id"):
            category = await db.categories.find_one({"_id": note["category_id"]})
            if category and category.get("color"):
                color_hex = category["color"]
        
        # Определение периода
        event_start = note.get("event_start")
        event_end = note.get("event_end")
        is_period = event_start != event_end if event_start and event_end else False
        
        event_data = {
            "id": f"note-{note_id}",
            "source": "note",
            "type": "note",
            "title": title,
            "date": event_start.date().isoformat() if event_start else "",
            "color": color_hex,
            "is_period": is_period,
            "content": note.get("content", ""),
            "link": f"#/notes/edit/{note_id}",
            "related_id": note_id,
            "category_id": str(note["category_id"]) if note.get("category_id") else None,
            "related_asset_id": str(note["related_asset_id"]) if note.get("related_asset_id") else None,
            "related_user_id": str(note["related_user_id"]) if note.get("related_user_id") else None,
            "created_by": str(note["created_by"]) if note.get("created_by") else None
        }
        
        # Добавляем end_date для периодов
        if is_period and event_end:
            event_data["end_date"] = event_end.date().isoformat()
        
        events.append(event_data)

    # Сортировка по дате
    events.sort(key=lambda item: item.get("date", ""))
    return events