from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
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
    model_config = ConfigDict(from_attributes=True)
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

class FilterNotice(BaseModel):
    name: Optional[str] = None
    source_file: Optional[str] = None
    oem_flag: Optional[str] = None
    itm_option: Optional[str] = None
    registration_number: Optional[str] = None

    list_filter_type_name: Optional[list] = None

    initial_sum_from: Optional[float] = None
    initial_sum_to: Optional[float] = None

    publication_datetime_from: Optional[datetime] = None
    publication_datetime_to: Optional[datetime] = None

    submission_start_datetime_from: Optional[datetime] = None
    submission_start_datetime_to: Optional[datetime] = None

    submission_close_datetime_from: Optional[datetime] = None
    submission_close_datetime_to: Optional[datetime] = None

    region_numbers: Optional[list[str]] = None

class UpdateNotice(BaseModel):
    name: Optional[str] = None
    filter_type_name: Optional[str] = None
    source_file: Optional[str] = None
    region_number: Optional[str] = None

    initial_sum: Optional[float] = None

    publication_datetime: Optional[datetime] = None
    submission_start_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None

    customer: Optional[Customer] = None
    contact: Optional[Contact] = None
    apply_request: Optional[ApplyRequest] = None

    result_info: Optional[dict] = None
    documents_list: Optional[list] = None

    lots: Optional[list[Lot]] = None
