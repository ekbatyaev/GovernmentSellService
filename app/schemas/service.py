from typing import Literal, Optional
from pydantic import BaseModel
from datetime import datetime

class AuthCode(BaseModel):
    guid: str
    email: str

    code: int

    created_at: datetime
    last_checked_at: datetime

class UpdateAuthCode(BaseModel):
    last_checked_at: datetime

class StatusAuthCode(BaseModel):
    status_message: Literal["try later", "not found", "not saved", "created"]
    guid: Optional[str] = None

class FilterAuthCode(BaseModel):
    email: Optional[str] = None

    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None

    last_checked_at_from: Optional[datetime] = None
    last_checked_at_to: Optional[datetime] = None
