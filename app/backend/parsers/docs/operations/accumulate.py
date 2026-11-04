from collections import OrderedDict
from app.backend.parsers.docs.config import FIELDS

FIELD_SETS = {1: FIELDS["rosseti"], 2: FIELDS["oem"], 3: FIELDS["itm"]}

def init_result_accumulator(field_mode: int = 1) -> dict:
    return {field: OrderedDict() for field in FIELD_SETS[field_mode]}

def init_documents_accumulator(documents_list_old=None) -> OrderedDict:
    result = OrderedDict()
    if documents_list_old is None:
        documents_list_old = []
    for doc in documents_list_old:
        name = str(doc).strip()
        if name:
            result[name] = None
    return result

def merge_extracted_into_accumulator(accumulator: dict, extracted: dict) -> None:
    if not extracted:
        return

    for field, value in extracted.items():
        if value is None:
            continue
        value = str(value).strip()
        if not value:
            continue

        for chunk in value.replace("\n", ";").split(";"):
            chunk = chunk.strip()
            if chunk:
                accumulator[field][chunk] = None

def add_processed_document(documents_accumulator, filename: str) -> None:
    filename = str(filename).strip()
    if filename:
        documents_accumulator[filename] = None

def finalize_result_accumulator(accumulator: dict) -> dict:
    return {field: "; ".join(values.keys()) if values else "" for field, values in accumulator.items()}

def finalize_documents_accumulator(documents_accumulator) -> list:
    return list(documents_accumulator.keys())

