from typing import Optional, Any
from datetime import datetime
from app.schemas.purchase import (Notice, Customer, Contact,
                                  ApplyRequest, Lot)

class UpdateNotice(Notice):
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


class FilterNotice(Notice):
    name: Optional[str] = None
    source_file: Optional[str] = None
    oem_flag: Optional[str] = None
    itm_option: Optional[str] = None

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


