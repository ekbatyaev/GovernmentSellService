from pydantic import BaseModel, EmailStr
from typing import Literal
from datetime import datetime

class User(BaseModel):
    guid: str
    email: EmailStr
    password: str

    role: Literal["admin", "user", "guest"]

    created_at: datetime