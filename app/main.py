import traceback
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.backend.scheduler.config import create_scheduler
from app.backend.database.settings import init_db, dispose_db
from app.routers.dependencies import hash_password
from app.settings import logger, settings, file_handler, MOSCOW_TZ
from app.routers.users.router import users_router
from app.routers.purchases.router import purchase_router
from app.routers.newsletters.router import newsletter_router
from app.routers.services.router import service_router
from app.settings import async_client_fastapi
from app.backend.parsers.request_archives import async_client
from fastapi.staticfiles import StaticFiles
from app.settings import BASE_DIR
from app.backend.database.functions import create_admin_user
from app.schemas.user import User

@asynccontextmanager
async def lifespan(app: FastAPI):

    scheduler = None

    try:
        logger.info("Инициализация приложения...")

        await init_db()

        scheduler = await create_scheduler()

        await create_admin_user(User(guid=str(uuid.uuid4()),
                                     email=settings.supervisor_system_email,
                                     password=hash_password(settings.supervisor_system_password),
                                     role="admin",
                                     created_at=datetime.now(MOSCOW_TZ).replace(tzinfo=None)))

        scheduler.start()

        os.makedirs(settings.tmp_dir, exist_ok=True)

        for uvicorn_logger_name in ("uvicorn.error", "uvicorn.access"):
            logging.getLogger(uvicorn_logger_name).addHandler(file_handler)

        logger.info("Startup complete (database + scheduler)")

        yield

    except Exception as exc:
        logger.error("Фатальная ошибка инициализации: %s", exc)
        logger.debug(traceback.format_exc())
        raise RuntimeError("Application initialization failed") from exc
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await dispose_db()
        await async_client.aclose()
        await async_client_fastapi.aclose()

app = FastAPI(title="Zakupki Database API",
    description="API для управления госзакупками", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (users_router, purchase_router, newsletter_router, service_router):
    app.include_router(router)

STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


    @app.get("/", include_in_schema=False)
    @app.get("/approve/{guid}", include_in_schema=False)
    async def spa_index(guid: str | None = None):
        return FileResponse(STATIC_DIR / "index.html")


    @app.get("/{name}.svg", include_in_schema=False)
    async def root_svg(name: str):
        return FileResponse(STATIC_DIR / f"{name}.svg")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
