import traceback
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.backend.scheduler import create_scheduler, run_backfill_on_startup
from app.backend.db.settings import init_db
from app.settings import logger, settings

@asynccontextmanager
async def lifespan(app: FastAPI):

    global scheduler

    try:
        logger.info("Инициализация приложения...")

        await init_db()

        scheduler = await create_scheduler()

        scheduler.start()

        # backfill 10 дней назад при старте

        await run_backfill_on_startup()

        logger.info("Startup complete (db + scheduler)")

        yield

    except Exception as exc:
        logger.error("Фатальная ошибка инициализации: %s", exc)
        logger.debug(traceback.format_exc())
        raise RuntimeError("Application initialization failed") from exc
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
            scheduler = None


app = FastAPI(title="Zakupki Database API",
    description="API для управления госзакупками", lifespan=lifespan)

app.mount(
    f"{settings.app_base}/assets",
    StaticFiles(directory="static/assets"),
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
