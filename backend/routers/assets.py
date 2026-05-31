import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.core.permissions import require_admin, require_permission
from backend.core.audit import log_action, snapshot, diff_changes
from backend.models.asset import AssetCreate, AssetUpdate, AssetResponse

def _asset_label(doc: Dict[str, Any]) -> str:
    return doc.get("name") or doc.get("inventory_number") or ""

logger = logging.getLogger("it_admin_backend")

router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Assets"],
    redirect_slashes=False
)

def convert_doc(doc: Dict[str, Any]) -> AssetResponse:

    safe_doc = dict(doc)
    safe_doc["id"] = str(safe_doc.pop("_id"))

    if "comments" in safe_doc and not isinstance(safe_doc["comments"], str):
        safe_doc["comments"] = None

    return AssetResponse(**safe_doc)

@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset: AssetCreate,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    asset_dict = asset.model_dump(exclude_none=True)

    if asset_dict.get("mol_user_id"):
        if not ObjectId.is_valid(asset_dict["mol_user_id"]):
            raise HTTPException(400, "Неверный формат ID пользователя (МОЛ)")

        mol_user = await db.users.find_one({
            "_id": ObjectId(asset_dict["mol_user_id"]),
            "is_active": True
        })
        if not mol_user:
            raise HTTPException(400, "Пользователь МОЛ не найден или неактивен")

        asset_dict["mol_name"] = mol_user["full_name"]

    asset_dict["created_by"] = current_user["id"]
    asset_dict["updated_by"] = current_user["id"]
    asset_dict["created_at"] = datetime.now(timezone.utc)
    asset_dict["updated_at"] = datetime.now(timezone.utc)

    try:
        result = await db.assets.insert_one(asset_dict)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Актив с таким инвентарным номером уже существует"
        )

    created_doc = await db.assets.find_one({"_id": result.inserted_id})
    if not created_doc:
        raise HTTPException(500, "Failed to retrieve created asset")

    await log_action(
        db, actor=current_user, action="create", entity_type="asset",
        entity_id=result.inserted_id, entity_label=_asset_label(created_doc),
        after=snapshot(created_doc),
    )
    return convert_doc(created_doc)

_ALLOWED_SORT_FIELDS = {
    "name", "inventory_number", "asset_type", "mol_name",
    "status", "commission_date", "warranty_end_date", "created_at",
}

@router.get("", response_model=List[AssetResponse])
async def get_assets(
    response: Response,
    skip: int = 0,
    limit: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    current_user: dict = Depends(require_permission("assets", "read")),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    total = await db.assets.count_documents({})
    response.headers["X-Total-Count"] = str(total)

    sort_field = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "created_at"
    direction = -1 if sort_order == "desc" else 1

    cursor = db.assets.find().sort(sort_field, direction)
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    return [convert_doc(doc) async for doc in cursor]

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: str,
    current_user: dict = Depends(require_permission("assets", "read")),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(asset_id):
        raise HTTPException(400, "Invalid ID")

    doc = await db.assets.find_one({"_id": ObjectId(asset_id)})
    if not doc:
        raise HTTPException(404, "Asset not found")
    return convert_doc(doc)

@router.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: str,
    update_data: AssetUpdate,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(asset_id):
        raise HTTPException(400, "Invalid ID")

    existing = await db.assets.find_one({"_id": ObjectId(asset_id)})
    if not existing:
        raise HTTPException(404, "Asset not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    if not update_dict:
        raise HTTPException(400, "No data to update")

    if "mol_user_id" in update_dict:
        if update_dict["mol_user_id"] is None:
            update_dict["mol_name"] = None
        else:
            if not ObjectId.is_valid(update_dict["mol_user_id"]):
                raise HTTPException(400, "Неверный формат ID пользователя (МОЛ)")
            mol_user = await db.users.find_one({
                "_id": ObjectId(update_dict["mol_user_id"]),
                "is_active": True
            })
            if not mol_user:
                raise HTTPException(400, "Пользователь МОЛ не найден или неактивен")
            update_dict["mol_name"] = mol_user["full_name"]

    update_dict["updated_at"] = datetime.now(timezone.utc)
    update_dict["updated_by"] = current_user["id"]

    result = await db.assets.update_one(
        {"_id": ObjectId(asset_id)},
        {"$set": update_dict}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Asset not found")

    updated_doc = await db.assets.find_one({"_id": ObjectId(asset_id)})
    if not updated_doc:
        raise HTTPException(404, "Asset not found after update")

    before, after = diff_changes(existing, update_dict)
    if after:
        await log_action(
            db, actor=current_user, action="update", entity_type="asset",
            entity_id=asset_id, entity_label=_asset_label(updated_doc),
            before=before, after=after,
        )
    return convert_doc(updated_doc)

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    if not ObjectId.is_valid(asset_id):
        raise HTTPException(400, "Invalid ID")

    doc = await db.assets.find_one({"_id": ObjectId(asset_id)})
    if not doc:
        raise HTTPException(404, "Asset not found")

    result = await db.assets.delete_one({"_id": ObjectId(asset_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Asset not found")

    await log_action(
        db, actor=current_user, action="delete", entity_type="asset",
        entity_id=asset_id, entity_label=_asset_label(doc),
        before=snapshot(doc),
    )
