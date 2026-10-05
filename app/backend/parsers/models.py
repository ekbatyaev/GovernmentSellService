from pydantic import BaseModel, Field

class ParseSoapResponse(BaseModel):
    code: int | None = None
    archive_urls: list = Field(default_factory=list )
    message: str | None = None

