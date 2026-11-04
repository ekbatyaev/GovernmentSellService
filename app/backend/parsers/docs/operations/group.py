from app.backend.parsers.docs.schemas import RarAnalysisInfo, Entry, GroupFileAnalysis
from app.schemas.purchase import Document
from app.backend.parsers.docs.operations.regex.rar import get_rar_group_info

def group_attached_files(attached_files: list[Document]) -> list[GroupFileAnalysis]:
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