from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
from app.settings import MOSCOW_TZ

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
    guid: str
    registration_number: str
    name: str
    filter_type_name: str
    region_number: str
    source_file: str

    customer: Customer
    contact: Contact
    apply_request: ApplyRequest
    result_info: dict
    documents_list: list
    lots: list[Lot]

    initial_sum: float

    publication_datetime: Optional[datetime] = Field(
        default_factory=lambda: (datetime.now(MOSCOW_TZ) - timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0, tzinfo=None
        )
    )

    submission_start_datetime: Optional[datetime] = Field(
        default_factory=lambda: (datetime.now(MOSCOW_TZ) - timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0, tzinfo=None
        )
    )

    submission_close_datetime: Optional[datetime] = Field(
        default_factory=lambda: (datetime.now(MOSCOW_TZ)).replace(
            hour=10, minute=0, second=0, microsecond=0, tzinfo=None
        )
    )