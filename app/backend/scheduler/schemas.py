from pydantic import BaseModel

class ResultDailyTask(BaseModel):
    status: bool = True

    created: int = 0
    updated: int = 0
    skipped: int = 0

    date: str