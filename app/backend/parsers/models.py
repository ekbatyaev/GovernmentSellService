from dataclasses import field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field, Field


class ParseSoapResponse(BaseModel):
    code: int | None = None
    archive_urls: list = field(default_factory=list)
    message: str | None = None

class Customer(BaseModel):
    full_name: str
    inn: int
    kpp: int
    ogrn: int

class Contact(BaseModel):
    last_name: str
    first_name: str
    middle_name: str
    phone: str
    email: str

class ApplyRequest(BaseModel):
    submission_order: str
    submission_place: str

class Document(BaseModel):
    filename: str
    description: str
    url: str

class Item(BaseModel):
    guid: str
    okpd2_code: str
    okpd2_name: str
    additional_info: str

class Lot(BaseModel):
    guid: str
    ordinal_number: str
    subject: str
    initial_sum: float
    currency: str
    items: Optional[list[Item]] = None

class Notice(BaseModel):
    guid: str = None
    region_number: int = None
    filter_type_name: str = None
    result_info: dict = None
    documents_list: list = None

    registration_number: str
    name: str
    publication_datetime: datetime

    submission_start_datetime: datetime | None
    submission_close_datetime: datetime | None

    customer: Customer
    contact: Contact

    apply_request: ApplyRequest

    attached_files: list[Document] = Field(exclude=True)
    lots: list[Lot]

    source_file: str

    @computed_field
    @property
    def initial_sum(self) -> float:
        return round(sum((lot.initial_sum for lot in self.lots), 0.0), 3)

