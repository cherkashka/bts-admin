from motor.motor_asyncio import AsyncIOMotorClient
from backend.core.config import settings
from backend.core.logging import logger

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.DB_NAME]

async def init_indexes():
    try:
        await db.users.create_index("username", unique=True)
        await db.users.update_many({"email": ""}, {"$set": {"email": None}})
        try:
            await db.users.drop_index("email_1")
        except Exception:
            pass
        await db.users.create_index(
            "email",
            unique=True,
            partialFilterExpression={"email": {"$type": "string"}},
            name="email_1",
        )

        # Одноразовая миграция: удаляем тестовых пользователей с префиксами rtest_/ui_test_
        await db.users.delete_many({
            "username": {"$regex": "^(rtest_|ui_test_)"}
        })

        # Проставляем новые поля существующим аккаунтам (идемпотентно)
        default_perms = {
            "assets":     {"create": False, "read": False, "update": False, "delete": False},
            "tasks":      {"create": False, "read": False, "update": False, "delete": False},
            "notes":      {"create": False, "read": False, "update": False, "delete": False},
            "categories": {"create": False, "read": False, "update": False, "delete": False},
        }
        await db.users.update_many(
            {"permissions": {"$exists": False}},
            {"$set": {"permissions": default_perms}}
        )
        await db.users.update_many(
            {"is_activated": {"$exists": False}},
            {"$set": {"is_activated": True}}
        )
        await db.users.update_many(
            {"password_change_required": {"$exists": False}},
            {"$set": {"password_change_required": False}}
        )
        await db.users.update_many(
            {"phone": {"$exists": False}},
            {"$set": {"phone": None}}
        )
        await db.assets.create_index("inventory_number", unique=True)
        await db.assets.create_index("asset_type")
        await db.assets.create_index("commission_date")
        await db.assets.create_index("warranty_end_date")
        await db.tasks.create_index("start_date")
        await db.tasks.create_index("event_start")
        await db.tasks.create_index("due_date")
        await db.tasks.create_index("deadline")
        # ===== Индексы для notes =====
        await db.notes.create_index("event_start")
        await db.notes.create_index("event_end")
        await db.notes.create_index("created_by")
        await db.notes.create_index("related_asset_id")
        await db.notes.create_index("related_user_id")
        await db.notes.create_index("category_id")  # Для связи с категориями
        
        # ===== Индексы для categories =====
        await db.categories.create_index("owner_id")
        await db.categories.create_index("name")
        await db.categories.create_index("is_default")
        
        logger.info("✅ Database indexes created/verified")
    except Exception as e:
        logger.error(f"⚠️ Index creation warning: {e}")

async def get_db():
    yield db