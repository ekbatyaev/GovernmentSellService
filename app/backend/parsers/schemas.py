from dataclasses import field
from datetime import datetime
from pydantic import BaseModel, computed_field, Field
from app.schemas.purchase import Notice, Document

class ParseSoapResponse(BaseModel):
    code: int | None = None
    archive_urls: list = field(default_factory=list)
    message: str | None = None

class NoticeParser(Notice):
    attached_files: list[Document] = Field(exclude=True)

    @computed_field
    @property
    def initial_sum(self) -> float:
        return round(sum((lot.initial_sum for lot in self.lots), 0.0), 3)

