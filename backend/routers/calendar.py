from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.core.permissions import is_admin
from datetime import datetime, date, timedelta
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
    tz_offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    start_date = parse_date(start, 'start')
    end_date = parse_date(end, 'end')

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail='Параметры start и end обязательны')

    if start_date > end_date:
        raise HTTPException(status_code=400, detail='Параметр start не может быть позже end')

    offset = timedelta(minutes=max(-840, min(840, tz_offset)))
    range_start = datetime.combine(start_date, datetime.min.time()) - offset
    range_end = datetime.combine(end_date, datetime.max.time()) - offset

    def local_day(dt: datetime) -> date:
        return (dt + offset).date()

    def in_range(day: date) -> bool:
        return start_date <= day <= end_date

    events: List[Dict[str, Any]] = []
    user_id = current_user["id"]
    user_is_admin = is_admin(current_user)

    show_assets = user_is_admin and not only_mine

    restrict_to_self = only_mine or not user_is_admin

    task_query = {
        "$or": [
            {"start_date": {"$gte": range_start}},
            {"event_start": {"$gte": range_start}},
            {"due_date": {"$gte": range_start}},
            {"deadline": {"$gte": range_start}}
        ],
        "$and": [
            {"$or": [
                {"start_date": {"$lte": range_end}},
                {"event_start": {"$lte": range_end}},
                {"due_date": {"$lte": range_end}},
                {"deadline": {"$lte": range_end}}
            ]}
        ]
    }

    if restrict_to_self:
        task_query["$and"].append({"assigned_to": user_id})

    cursor = db.tasks.find(task_query)
    async for task in cursor:
        task_id = str(task.get("_id"))
        title = task.get("title", "Задача")

        start_value = task.get("start_date") or task.get("event_start")
        if start_value:
            day = local_day(start_value)
            if in_range(day):
                events.append({
                    "id": f"task-start-{task_id}",
                    "source": "task",
                    "type": "task_start",
                    "title": "Начало задачи: " + title,
                    "date": day.isoformat(),
                    "link": "#/tasks",
                    "related_id": task_id
                })

        due_value = task.get("due_date") or task.get("deadline")
        if due_value:
            day = local_day(due_value)
            if in_range(day):
                events.append({
                    "id": f"task-due-{task_id}",
                    "source": "task",
                    "type": "task_due",
                    "title": "Дедлайн задачи: " + title,
                    "date": day.isoformat(),
                    "link": "#/tasks",
                    "related_id": task_id
                })

    if show_assets:
        asset_query = {
            "$or": [
                {"commission_date": {"$gte": range_start}},
                {"warranty_end_date": {"$gte": range_start}}
            ],
            "$and": [
                {"$or": [
                    {"commission_date": {"$lte": range_end}},
                    {"warranty_end_date": {"$lte": range_end}}
                ]}
            ]
        }

        cursor = db.assets.find(asset_query)
        async for asset in cursor:
            asset_id = str(asset.get("_id"))
            name = asset.get("name", "Актив")

            if asset.get("commission_date"):
                day = local_day(asset["commission_date"])
                if in_range(day):
                    events.append({
                        "id": f"asset-commission-{asset_id}",
                        "source": "asset",
                        "type": "commission",
                        "title": "Ввод в эксплуатацию: " + name,
                        "date": day.isoformat(),
                        "link": f"#/assets/edit/{asset_id}",
                        "related_id": asset_id
                    })

            if asset.get("warranty_end_date"):
                day = local_day(asset["warranty_end_date"])
                if in_range(day):
                    events.append({
                        "id": f"asset-warranty-{asset_id}",
                        "source": "asset",
                        "type": "warranty_end",
                        "title": "Окончание гарантии: " + name,
                        "date": day.isoformat(),
                        "link": f"#/assets/edit/{asset_id}",
                        "related_id": asset_id
                    })

    notes_query = {
        "$or": [
            {
                "event_start": {
                    "$gte": range_start,
                    "$lte": range_end
                }
            },
            {
                "event_end": {
                    "$gte": range_start,
                    "$lte": range_end
                }
            },
            {
                "event_start": {"$lte": range_start},
                "event_end": {"$gte": range_end}
            }
        ]
    }

    if restrict_to_self:
        notes_query["created_by"] = ObjectId(user_id)

    cursor = db.notes.find(notes_query)
    async for note in cursor:
        note_id = str(note.get("_id"))
        title = note.get("title", "Запись")

        event_start = note.get("event_start")
        event_end = note.get("event_end")
        if not event_start:
            continue

        start_day = local_day(event_start)
        end_day = local_day(event_end) if event_end else start_day
        if end_day < start_day:
            end_day = start_day

        if end_day < start_date or start_day > end_date:
            continue

        color_hex = "#3b82f6"
        if note.get("category_id"):
            category = await db.categories.find_one({"_id": note["category_id"]})
            if category and category.get("color"):
                color_hex = category["color"]

        is_period = end_day != start_day

        event_data = {
            "id": f"note-{note_id}",
            "source": "note",
            "type": "note",
            "title": title,
            "date": start_day.isoformat(),
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

        if is_period:
            event_data["end_date"] = end_day.isoformat()

        events.append(event_data)

    events.sort(key=lambda item: item.get("date", ""))
    return events
