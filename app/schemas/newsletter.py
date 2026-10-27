from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, Literal

class NewsLetter(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    guid: str
    email: EmailStr
    filter_type_name: str
    district_name: Optional[str] = ""

class FilterNewsLetters(BaseModel):
    list_filter_type_names: Optional[list] = None
    list_district_names: Optional[list] = None
    list_emails: Optional[list] = None

class UpdateNewsLetter(BaseModel):
    email: Optional[str] = None
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None

class ConfirmOptionNewsLetter(BaseModel):
    guid: str
    filter_type_name: str
    district_name: Optional[str] = ""

    option: Literal["subscribe", "unsubscribe"]

    code: int

    email: EmailStr
