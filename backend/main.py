from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.core.config import settings
from backend.core.database import client, init_indexes

@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.admin.command("ping")
    await init_indexes()
    await cleanup_legacy_starter_categories()
    yield
    client.close()

async def cleanup_legacy_starter_categories():
    from backend.core.database import db
    from bson import ObjectId

    legacy_names = ["Работа", "Встречи", "Личное", "Напоминания", "Срочно"]
    legacy_cats = await db.categories.find(
        {"name": {"$in": legacy_names}, "owner_id": None}
    ).to_list(length=100)

    for cat in legacy_cats:
        in_use = await db.notes.count_documents({"category_id": cat["_id"]})
        if in_use == 0:
            await db.categories.delete_one({"_id": cat["_id"]})

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,

    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,

    allow_origin_regex=r"http://(127\.0\.0\.1|localhost|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
)

from backend.routers.auth import router as auth_router
from backend.routers.assets import router as assets_router
from backend.routers.users import router as users_router
from backend.routers.tasks import router as tasks_router
from backend.routers.calendar import router as calendar_router
from backend.routers.notes import router as notes_router
from backend.routers.categories import router as categories_router
from backend.routers.export import router as export_router
from backend.routers.audit import router as audit_router

app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(users_router)
app.include_router(tasks_router)
app.include_router(calendar_router)
app.include_router(notes_router)
app.include_router(categories_router)
app.include_router(export_router)
app.include_router(audit_router)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
