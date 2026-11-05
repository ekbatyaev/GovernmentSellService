from pydantic import BaseModel
from typing import Literal, Optional
from pathlib import Path
from app.schemas.purchase import Document

class AnalyzeStats(BaseModel):
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0

class ProcessStats(BaseModel):
    stats: Optional[AnalyzeStats] = None
    source_url: Optional[str] = None
    error: Optional[str] = None

class ExtractInfo(BaseModel):
    path: Path
    text: Optional[str] = None
    error: Optional[str] = None

class Entry(BaseModel):
    doc: Document
    part_num: Optional[int] = None
    is_start: Optional[bool] = None
    base: Optional[str] = None

class GroupFileAnalysis(BaseModel):
    group_type: Literal["multipart_rar", "single"]
    base: Optional[str] = None
    scheme: Optional[Literal["part", "oldstyle"]] = None
    parts: list[Entry]

class RarAnalysisInfo(BaseModel):
    scheme: Literal["part", "oldstyle_subpart", "oldstyle_main"]
    base: str
    part_num: int
    is_start: bool