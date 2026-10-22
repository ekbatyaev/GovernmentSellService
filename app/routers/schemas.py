from typing import Any, Literal
from pydantic import BaseModel

class ResponseModel(BaseModel):
    status_message: Literal["success", "created", "deleted",
                                "updated", "found", "not found"]
    data: Any