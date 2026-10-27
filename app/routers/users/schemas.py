from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import User
from typing import Optional, Literal


class UpdateUser(User):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[Literal["admin", "user", "guest"]] = None

class ConfirmEmailUser(BaseModel):
    email: EmailStr

class RegisterUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class ApproveUser(BaseModel):
    user_role: Literal["admin", "user", "guest"]