from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Literal, Optional
from datetime import datetime

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    guid: str
    email: EmailStr
    password: str

    role: Literal["admin", "user", "guest"]

    created_at: datetime

class FilterUser(BaseModel):
    email: Optional[str] = None

    role: Optional[Literal["admin", "user", "guest"]] = None

    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None