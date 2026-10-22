from typing import Optional
from app.schemas.email import NewsLetter
from pydantic import BaseModel

class FilterNewsLetters(NewsLetter):
    list_filter_type_names: Optional[str] = None
    list_district_names: Optional[str] = None
    list_emails: Optional[str] = None

class UpdateNewsLetter(NewsLetter):
    email: Optional[str] = None
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None

class VerifyCodeNewsLetter(BaseModel):
    code: int