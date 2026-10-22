from pydantic import BaseModel
from typing import Optional

class NewsLetter(BaseModel):
    guid: str
    email: str
    filter_type_name: str
    district_name: Optional[str] = ""