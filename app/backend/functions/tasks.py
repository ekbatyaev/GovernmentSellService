from app.settings import logger
from fastapi import HTTPException, BackgroundTasks

# Состояние текущей фоновой задачи админки. status: idle | running | done | error
current_job: dict = {"name": None, "status": "idle", "message": None}

async def run_job(name: str, func, *args, **kwargs):
    global current_job
    try:
        await func(*args, **kwargs)
        current_job.update(name=name, status="done", message= f"{name}: завершено")
    except Exception as e:
        logger.exception("Фоновая задача %s упала", name)
        current_job.update(name=name, status="error", message=f"{name}: {e}")


def start_job(background: BackgroundTasks, name: str, func, *args, **kwargs):
    global current_job
    if current_job["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Уже выполняется задача {current_job['name']}, пожалуйста, попробуйте позже.")
    current_job.update(name=name, status="running", message=None)
    background.add_task(run_job, name, func, *args, **kwargs)
