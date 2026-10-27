from pydantic import BaseModel

class GroupsRegNumbers(BaseModel):
    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []