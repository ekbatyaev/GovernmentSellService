from pydantic import BaseModel, EmailStr, Field
from typing import Literal

class ConfirmEmailUser(BaseModel):
    email: EmailStr

class RegisterUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    code: int

class ApproveUser(BaseModel):
    role: Literal["admin", "user", "guest"]
