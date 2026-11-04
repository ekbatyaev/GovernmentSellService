from app.backend.parsers.docs.schemas import RarAnalysisInfo
import re

RAR_PART_RE = re.compile(r"^(?P<base>.+)\.part(?P<part>\d+)\.rar$", re.IGNORECASE)
RAR_OLDSTYLE_MAIN_RE = re.compile(r"^(?P<base>.+)\.rar$", re.IGNORECASE)
RAR_OLDSTYLE_SUBPART_RE = re.compile(r"^(?P<base>.+)\.r(?P<part>\d{2})$", re.IGNORECASE)

def is_rar_part_filename(name: str) -> bool:
    name = (name or "").strip()
    return bool(RAR_PART_RE.match(name) or RAR_OLDSTYLE_SUBPART_RE.match(name))

def get_rar_group_info(filename: str) -> RarAnalysisInfo | None:
    filename = (filename or "")

    m = RAR_PART_RE.match(filename)
    if m:
        part = int(m.group("part"))
        return RarAnalysisInfo(**{"scheme": "part", "base": m.group("base"),
                                  "part_num": part, "is_start": part == 1})

    m = RAR_OLDSTYLE_SUBPART_RE.match(filename)
    if m:
        return RarAnalysisInfo(**{
            "scheme": "oldstyle_subpart",
            "base": m.group("base"),
            "part_num": int(m.group("part")) + 1,
            "is_start": False,
        })

    m = RAR_OLDSTYLE_MAIN_RE.match(filename)
    if m:
        return RarAnalysisInfo(**{"scheme": "oldstyle_main", "base": m.group("base"),
                                  "part_num": 0, "is_start": True})
    return None