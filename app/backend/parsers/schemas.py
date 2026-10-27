from typing import Any
from pydantic import BaseModel, Field, model_validator
from app.schemas.purchase import Notice, Document, Lot, Item

class ParseSoapResponse(BaseModel):
    code: int | None = None
    archive_urls: list = Field(default_factory=list)
    message: str | None = None

class NoticeParser(Notice):
    """Notice на этапе разбора XML: guid, тип фильтра и регион проставляются позже,
    а initial_sum считается как сумма лотов."""

    guid: str = ""
    filter_type_name: str = ""
    region_number: str = ""
    result_info: dict = Field(default_factory=dict)
    documents_list: list = Field(default_factory=list)

    attached_files: list[Document] = Field(default_factory=list, exclude=True)

    # Пустые даты из XML ('' / None) убираем, чтобы сработали default_factory из Notice:
    # колонки дат в БД NOT NULL, а '' не парсится в datetime.
    @model_validator(mode="before")
    @classmethod
    def _drop_empty_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = {k: v for k, v in data.items()
                    if not (k.endswith("_datetime") and v in ("", None))}
        return data

    # Pydantic не даёт перекрыть поле родителя computed_field-ом, поэтому
    # заполняем initial_sum до валидации, если его не передали явно.
    @model_validator(mode="before")
    @classmethod
    def _fill_initial_sum(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("initial_sum") is None:
            total = 0.0
            for lot in data.get("lots") or []:
                value = lot.get("initial_sum") if isinstance(lot, dict) else getattr(lot, "initial_sum", 0)
                total += float(value or 0)
            data = {**data, "initial_sum": round(total, 3)}
        return data
