from collections import OrderedDict
from app.backend.parsers.docs.config import FIELDS
from app.backend.parsers.docs.schemas import RarAnalysisInfo, Entry, GroupFileAnalysis
from app.schemas.purchase import Document
from app.backend.parsers.docs.operations.regex.rar import get_rar_group_info

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

def accumulate_attached_files(attached_files: list[Document]) -> list[GroupFileAnalysis]:
    list_group_file_analysis = []
    part_groups: dict[str, list[Entry]] = {}
    oldstyle_main: dict[str, Entry] = {}
    oldstyle_subparts: dict[str, list[Entry]] = {}

    for doc in attached_files:
        info: RarAnalysisInfo = get_rar_group_info(doc.filename.strip())

        if not info:
            entry = Entry(doc=doc)
            list_group_file_analysis.append(
                GroupFileAnalysis(group_type="single", parts=[entry]))
            continue

        entry = Entry(
            doc=doc,
            part_num=info.part_num,
            is_start=info.is_start,
            base=info.base
        )

        if info.scheme == "part":
            part_groups.setdefault(info.base, []).append(entry)
        elif info.scheme == "oldstyle_main":
            oldstyle_main[info.base] = entry
        elif info.scheme == "oldstyle_subpart":
            oldstyle_subparts.setdefault(info.base, []).append(entry)

    for base, parts in part_groups.items():
        parts.sort(key=lambda x: x.part_num)
        list_group_file_analysis.append(GroupFileAnalysis(**{"group_type": "multipart_rar",
                                                             "base": base, "scheme": "part", "parts": parts}))

    for base, subparts in oldstyle_subparts.items():
        parts = ([oldstyle_main[base]] if base in oldstyle_main else []) + subparts
        parts.sort(key=lambda x: x.part_num)
        list_group_file_analysis.append(GroupFileAnalysis(**{"group_type": "multipart_rar",
                                                             "base": base, "scheme": "oldstyle", "parts": parts}))

    # Одиночные .rar без сопутствующих томов.
    for base, entry in oldstyle_main.items():
        if base not in oldstyle_subparts:
            list_group_file_analysis.append(GroupFileAnalysis(**{"group_type": "single", "parts": [entry]}))

    return list_group_file_analysis
