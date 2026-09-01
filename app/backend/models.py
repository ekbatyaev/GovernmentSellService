from datetime import datetime
from typing import Optional, Any, List
from pydantic import BaseModel

class PutPurchaseModel(BaseModel):
    token: str
    guid: str
    registration_number: str
    name: str
    filter_type_name: str
    source_file: Optional[str] = None
    initial_sum: Optional[float] = None
    publication_datetime: Optional[datetime] = None
    submission_start_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None
    customer: Any
    contact: Any
    apply_request: Any
    result_info: Any
    documents_list: List[Any]

    region_number: Optional[str] = None

    lots: List[Any]


class DeletePurchaseModel(BaseModel):
    token: str
    filter_type_name: Optional[str] = None
    region_number: Optional[str] = None
    guid: str


class GetPurchaseModel(BaseModel):
    token: str
    registration_number: Optional[str] = None
    filter_type_name: Optional[str] = None
    guid: Optional[str] = None
    region_number: Optional[str] = None


class GetAllPurchasesModel(BaseModel):
    token: str
    name: Optional[str] = None
    initial_sum_from: Optional[float] = None
    initial_sum_to: Optional[float] = None

    publication_datetime_from: Optional[datetime] = None
    publication_datetime_to: Optional[datetime] = None

    submission_start_datetime_from: Optional[datetime] = None
    submission_start_datetime_to: Optional[datetime] = None

    submission_close_datetime_from: Optional[datetime] = None
    submission_close_datetime_to: Optional[datetime] = None
    source_file: Optional[str] = None

    filter_type_name: Optional[str] = None
    region_number: Optional[str] = None

    region_numbers: Optional[list[str]] = None
    oem_flag: Optional[str] = None
    itm_option: Optional[str] = None

class UpdatePurchaseModel(BaseModel):
    token: str
    guid: Optional[str] = None
    registration_number: Optional[str] = None
    filter_type_name: Optional[str] = None
    name: Optional[str] = None
    source_file: Optional[str] = None
    initial_sum: Optional[float] = None
    publication_datetime: Optional[datetime] = None
    submission_start_datetime: Optional[datetime] = None
    submission_close_datetime: Optional[datetime] = None
    customer: Optional[Any] = None
    contact: Optional[Any] = None
    apply_request: Optional[Any] = None
    result_info: Optional[Any] = None
    documents_list: Optional[Any] = None
    lots: Optional[Any] = None
    region_number: Optional[str] = None


class PurchaseResponseModel(BaseModel):
    guid: str
    registration_number: Optional[str]
    name: str
    source_file: Optional[str]
    initial_sum: Optional[float]
    publication_datetime: Optional[datetime]
    submission_start_datetime: Optional[datetime]
    submission_close_datetime: Optional[datetime]
    customer: Any
    contact: Any
    apply_request: Any
    result_info: Any
    documents_list: List[Any]
    lots: List[Any]
    filter_type_name: Optional[str]
    region_number: Optional[str]

    class Config:
        from_attributes = True


class SuccessResponseModel(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None

class AdminTokenModel(BaseModel):
    token: str

class AdminBackfillModel(BaseModel):
    token: str
    filter_number: Optional[int]
    days: Optional[int] = None

class DeleteExpiredModel(BaseModel):
    token: str

class AdminProcessDay(BaseModel):
    token: str
    filter_number: Optional[int]
    date: datetime

class AdminProcessPeriodOfTime(BaseModel):
    token: str
    filter_number: Optional[int]
    date_from: datetime
    date_to: datetime

class PutNewsLetterModel(BaseModel):
    token: str
    filter_type_name: str
    district_name: Optional[str] = ""
    email: str

class DeleteNewsLetterModel(BaseModel):
    token: str
    email: str
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None

class GetNewsLetterModel(BaseModel):
    token: str
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None
    email: str

class GetAllNewsLettersModel(BaseModel):
    token: str
    filter_type_name: Optional[str] = None
    district_name: Optional[str] = None

class BaseTokenModel(BaseModel):
    token: str

class SendAuthCode(BaseModel):
    token: str
    email: str

class VerifyCode(BaseModel):
    token: str
    email: str
    code: int