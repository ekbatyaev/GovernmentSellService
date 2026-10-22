from typing import Optional, Literal
from app.schemas.email import NewsLetter

class FilterNewsLetters(NewsLetter):
    list_filter_type_names: Optional[str] = None
    list_district_names: Optional[str] = None
    list_emails: Optional[str] = None

class UpdateNewsLetter(NewsLetter):
    email: Optional[str] = None
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None

class ConfirmOptionNewsLetter(NewsLetter):
    guid: str
    option: Literal["subscribe", "unsubscribe"]
    code: int