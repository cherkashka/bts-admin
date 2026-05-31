
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from backend.core.config import settings

COLOR_TO_CATEGORY = {
    "red": "Красный",
    "orange": "Оранжевый",
    "yellow": "Жёлтый",
    "green": "Зелёный",
    "blue": "Синий",
    "purple": "Фиолетовый",
    "gray": "Серый"
}

DEFAULT_CATEGORIES = [
    {"name": "Работа", "color": "#3b82f6", "icon": "💼", "is_default": True},
    {"name": "Встречи", "color": "#8b5cf6", "icon": "👥", "is_default": True},
    {"name": "Личное", "color": "#22c55e", "icon": "🏠", "is_default": True},
    {"name": "Напоминания", "color": "#f59e0b", "icon": "🔔", "is_default": True},
    {"name": "Срочно", "color": "#ef4444", "icon": "⚡", "is_default": True},
]

async def seed_default_categories(db):
    print("🌱 Создание предустановленных категорий...")

    for cat in DEFAULT_CATEGORIES:
        existing = await db.categories.find_one({"name": cat["name"], "is_default": True})
        if not existing:
            result = await db.categories.insert_one({
                **cat,
                "owner_id": None,
                "created_at": None,
                "updated_at": None
            })
            print(f"   ✓ Создана категория: {cat['name']} ({cat['color']})")
        else:
            print(f"   → Уже существует: {cat['name']}")

    print("✅ Предустановленные категории готовы")

async def migrate_notes(db):
    print("\n🔄 Миграция заметок (color → category_id)...")

    color_categories = {}
    for color_name, category_name in COLOR_TO_CATEGORY.items():

        existing = await db.categories.find_one({
            "name": category_name,
            "is_default": True
        })

        if existing:
            color_categories[color_name] = existing["_id"]
            print(f"   → Категория для '{color_name}': {category_name} (существует)")
        else:

            from backend.models.note import COLOR_HEX_MAP
            color_hex = COLOR_HEX_MAP.get(color_name, "#6b7280")

            result = await db.categories.insert_one({
                "name": category_name,
                "color": color_hex,
                "icon": None,
                "is_default": True,
                "owner_id": None,
                "created_at": None,
                "updated_at": None
            })
            color_categories[color_name] = result.inserted_id
            print(f"   ✓ Создана категория: {category_name} ({color_hex})")

    cursor = db.notes.find({"color": {"$exists": True}})
    updated_count = 0
    skipped_count = 0

    async for note in cursor:
        color = note.get("color")
        if color in color_categories:
            category_id = color_categories[color]
            result = await db.notes.update_one(
                {"_id": note["_id"]},
                {
                    "$set": {"category_id": category_id},
                    "$unset": {"color": ""}
                }
            )
            if result.modified_count > 0:
                updated_count += 1
        else:
            skipped_count += 1

    print(f"\n✅ Миграция завершена:")
    print(f"   • Обновлено записей: {updated_count}")
    print(f"   • Пропущено (неизвестный цвет): {skipped_count}")

async def main():
    print("🚀 Запуск миграции заметок на категории")
    print(f"📡 Подключение к: {settings.MONGO_URI[:30]}...")

    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.DB_NAME]

    try:

        await seed_default_categories(db)

        await migrate_notes(db)

        print("\n✨ Все операции завершены успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        raise
    finally:
        client.close()
        print("🔌 Подключение к БД закрыто")

if __name__ == "__main__":
    asyncio.run(main())
