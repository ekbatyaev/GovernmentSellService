import traceback
import logging
import os
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.backend.scheduler import create_scheduler, run_backfill
from app.backend.db.settings import init_db, dispose_db
from app.settings import logger, settings, BASE_DIR, file_handler

@asynccontextmanager
async def lifespan(app: FastAPI):

    scheduler = None

    try:
        logger.info("Инициализация приложения...")

        await init_db()

        scheduler = await create_scheduler()

        scheduler.start()

        if settings.backfill_on_startup:
            await run_backfill(settings.backfill_days)

        os.makedirs(settings.tmp_dir, exist_ok=True)

        for uvicorn_logger_name in ("uvicorn.error", "uvicorn.access"):
            logging.getLogger(uvicorn_logger_name).addHandler(file_handler)

        logger.info("Startup complete (db + scheduler)")

        yield

    except Exception as exc:
        logger.error("Фатальная ошибка инициализации: %s", exc)
        logger.debug(traceback.format_exc())
        raise RuntimeError("Application initialization failed") from exc
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        await dispose_db()


app = FastAPI(title="Zakupki Database API",
    description="API для управления госзакупками", lifespan=lifespan)

app.mount(
    f"{settings.app_base}/assets",
    StaticFiles(directory=str(BASE_DIR / "static" / "assets")),
    name="assets",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app import routers  # noqa: E402  — импорт регистрирует роуты через декораторы

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
