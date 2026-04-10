import re
from typing import Dict, List, Optional


ORG_PATTERN = r'(?:ООО|АО|ПАО|ИП)\s+[«"][^»"]+[»"](?:\s*\([^)]*\))?'


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[ ]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    return text.strip()


def normalize_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"[ \t]+", " ", value).strip(" \n\t:;-")
    return value or None


def cleanup_org(name: Optional[str], keep_address: bool = False) -> Optional[str]:
    name = normalize_value(name)
    if not name:
        return None
    if not keep_address:
        name = re.sub(r"\s*\([^)]*\)", "", name).strip()
    return name or None


def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def find_first(patterns: List[str], text: str, flags=re.IGNORECASE | re.MULTILINE) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, flags)
        if not m:
            continue
        if m.lastindex:
            for group in m.groups():
                val = normalize_value(group)
                if val:
                    return val
        else:
            val = normalize_value(m.group(0))
            if val:
                return val
    return None


def find_all(pattern: str, text: str, flags=re.IGNORECASE | re.MULTILINE) -> List[str]:
    matches = re.findall(pattern, text, flags)
    result = []
    for m in matches:
        if isinstance(m, tuple):
            val = " ".join(str(x).strip() for x in m if x and str(x).strip())
        else:
            val = str(m).strip()
        val = normalize_value(val)
        if val:
            result.append(val)
    return result


def extract_between(text: str, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if m:
            val = normalize_value(m.group(1))
            if val:
                return val
    return None


def extract_participants_block(text: str) -> Optional[str]:
    return extract_between(text, [
        r'ПОСТУПИВШИЕ ЗАЯВКИ\s*:\s*(.*?)\s*ВОПРОСЫ КОМИССИИ',
        r'ПОСТУПИВШИЕ ЗАЯВКИ\s*:\s*(.*?)\s*РЕШИЛИ',
        r'ПОСТУПИВШИЕ ЗАЯВКИ\s*(.*?)\s*ВОПРОСЫ КОМИССИИ',
        r'ПОСТУПИВШИЕ ЗАЯВКИ\s*(.*?)\s*РЕШИЛИ',
    ])


def extract_organizations(text: str) -> List[str]:
    if not text:
        return []

    patterns = [
        r'\bООО\s+[«"][^»"]+[»"](?:\s*\([^)]*\))?',
        r'\bАО\s+[«"][^»"]+[»"](?:\s*\([^)]*\))?',
        r'\bПАО\s+[«"][^»"]+[»"](?:\s*\([^)]*\))?',
        r'\bИП\s+[А-ЯЁA-Z][А-ЯЁа-яёA-Za-z.\- ]+',
    ]

    found = []
    for p in patterns:
        found.extend(find_all(p, text, flags=re.IGNORECASE | re.MULTILINE))

    cleaned = []
    seen = set()
    for item in found:
        item = cleanup_org(item, keep_address=False)
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)

    return cleaned


def extract_winner_direct(text: str) -> Optional[str]:
    patterns = [
        rf'Признать Победителем закупки\s+({ORG_PATTERN})\s+на следующих условиях',
        rf'заключить договор с\s+({ORG_PATTERN})\s*на выполнение',
        rf'победителем признан[а-я]*\s+({ORG_PATTERN})',
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if m:
            winner = cleanup_org(m.group(1), keep_address=False)
            if winner:
                return winner
    return None


def extract_winner_from_ranking(text: str) -> Optional[str]:
    rank_patterns = [
        rf'Место в ранжире.*?\n1[\t ]+({ORG_PATTERN})(?:[\t ]+|\n|$)',
        rf'Наименование Участника.*?\n1[\t ]+({ORG_PATTERN})(?:[\t ]+|\n|$)',
    ]

    for pattern in rank_patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if m:
            winner = cleanup_org(m.group(1), keep_address=False)
            if winner:
                return winner

    for line in text.splitlines():
        line = line.strip()

        m = re.match(rf'^1[\t ]+({ORG_PATTERN})(?:[\t ]+|$)', line, re.IGNORECASE)
        if m:
            winner = cleanup_org(m.group(1), keep_address=False)
            if winner:
                return winner

        cols = [c.strip() for c in line.split("\t") if c.strip()]
        if len(cols) >= 2 and cols[0] == "1":
            m2 = re.match(rf'^({ORG_PATTERN})$', cols[1], re.IGNORECASE)
            if m2:
                winner = cleanup_org(m2.group(1), keep_address=False)
                if winner:
                    return winner

    return None


def extract_typ_project(text: str) -> Optional[str]:
    patterns = [
        r'Строительство\s+(БКТП-\d+/\d+,\d+\s*кВ\s+с\s+тр-ми\s*[\dxхX]+\s*кВА)',
        r'Строительство\s+(БКТП-\d+/\d+,\d+\s*кВ)',
        r'(БКТП-\d+/\d+,\d+\s*кВ\s+с\s+тр-ми\s*[\dxхX]+\s*кВА)',
        r'(БКТП-\d+/\d+,\d+\s*кВ)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return normalize_value(m.group(1))
    return None


def extract_designer(text: str) -> Optional[str]:
    patterns = [
        r'Проектировщик\s*[:\-]\s*(.+)',
        r'Проектная организация\s*[:\-]\s*(.+)',
        r'Разработчик проекта\s*[:\-]\s*(.+)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = normalize_value(m.group(1))
            if val:
                return val
    return None


def extract_cells_unique(text: str):
    nums = re.findall(r'\bяч\.\s*(\d+)\b', text, flags=re.IGNORECASE)
    unique = []
    seen = set()
    for n in nums:
        if n not in seen:
            seen.add(n)
            unique.append(n)
    if not unique:
        return None, None
    return "; ".join(f"яч.{n}" for n in unique), str(len(unique))


def extract_tender_fields(text: str) -> Dict[str, Optional[str]]:
    text = clean_text(text)

    result = {
        "Победитель": None,
        "Другие участники": None,
        "Ячейки": None,
        "Кол-во ячеек": None,
        "Типовой проект": None,
        "Проектировщик": None,
        "Дата исполнения договора": None,
        "Филиал/РЭС": None,
    }

    winner = extract_winner_direct(text) or extract_winner_from_ranking(text)
    result["Победитель"] = winner

    participants_block = extract_participants_block(text)
    participants = extract_organizations(participants_block) if participants_block else []
    if participants:
        others = [p for p in participants if p != winner]
        others = unique_keep_order(others)
        if others:
            result["Другие участники"] = "; ".join(others)

    exec_date = find_first([
        r'С даты подписания договора\s*-\s*по\s*(\d{2}[./]\d{2}[./]\d{4})',
        r'С даты подписания договора\s*\n\s*-\s*по\s*(\d{2}[./]\d{2}[./]\d{4})',
        r'Срок выполнения работ.*?по\s*(\d{2}[./]\d{2}[./]\d{4})',
        r'Дата исполнения договора[:\s]+(\d{2}[./]\d{2}[./]\d{4})',
    ], text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if exec_date:
        result["Дата исполнения договора"] = exec_date.replace(".", "/")

    filial = find_first([
        r'для нужд\s+([А-ЯA-ZЁ\-]{1,20})\s*-\s*филиала',
        r'([А-ЯA-ZЁ\-]{1,20})\s*-\s*филиалу ПАО',
        r'([А-ЯA-ZЁ\-]{1,20})\s*-\s*филиала ПАО',
    ], text)
    if filial:
        result["Филиал/РЭС"] = filial

    cells, cells_count = extract_cells_unique(text)
    result["Ячейки"] = cells
    result["Кол-во ячеек"] = cells_count

    result["Типовой проект"] = extract_typ_project(text)
    result["Проектировщик"] = extract_designer(text)

    return result