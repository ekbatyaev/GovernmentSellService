from typing import Literal, Optional
from pydantic import BaseModel

class StatusAuthCode(BaseModel):
    status_message: Literal["try later", "not found", "not saved", "created"]
    guid: Optional[str] = None