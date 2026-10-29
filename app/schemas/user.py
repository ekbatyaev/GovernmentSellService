from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Literal, Optional
from datetime import datetime

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    guid: str
    email: EmailStr
    password: str

    role: Literal["admin", "user", "guest"]

    created_at: datetime

class UpdateUser(BaseModel):
    email: Optional[EmailStr] = None

    password: Optional[str] = None

    role: Optional[Literal["admin", "user", "guest"]] = None

class RecoverPasswordUser(BaseModel):
    email: EmailStr

    code: int

    password: str = Field(min_length=8, max_length=128)

class ChangePasswordUser(BaseModel):
    current_password: str

    new_password: str = Field(min_length=8, max_length=128)

class LoginUser(BaseModel):
    status: Literal["invalid", "updated"]
    payload: Optional[str] = None

class FilterUser(BaseModel):
    email: Optional[str] = None

    role: Optional[Literal["admin", "user", "guest"]] = None

    created_at_from: Optional[datetime] = None
    created_at_to: Optional[datetime] = None
