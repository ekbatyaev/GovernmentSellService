from pydantic import BaseModel

class ItmFilter(BaseModel):
    result: bool
    reason: str
    filter_name: str
    component: list
    brand: list
    work_patterns: list
    normalized_text: str

class OemFilter(BaseModel):
    result: bool
    reason: str
    force_exclude: list
    force_include: list
    object: list
    component: list
    brand: list
    controlled_object: list
    exclude_hard: list
    exclude_soft: list

class RossetiFilter(BaseModel):
    result: bool
    ok_customer: bool
    ok_job: bool
    excluded_job: bool
    reason: str