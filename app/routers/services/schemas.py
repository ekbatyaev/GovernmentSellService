from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProcessDay(BaseModel):
    filter_number: Optional[int] = None

class ProcessDayService(ProcessDay):
    date: datetime

class ProcessPeriodService(ProcessDay):
    date_from: datetime
    date_to: datetime
