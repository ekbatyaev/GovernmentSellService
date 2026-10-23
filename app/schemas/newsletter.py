from pydantic import BaseModel, EmailStr
from typing import Optional

class NewsLetter(BaseModel):
    guid: str
    email: EmailStr
    filter_type_name: str
    district_name: Optional[str] = ""