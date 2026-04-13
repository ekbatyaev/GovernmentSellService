from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from dateparser.search import search_dates
from natasha import (
    Doc,
    MorphVocab,
    NewsEmbedding,
    NewsMorphTagger,
    NewsNERTagger,
    Segmenter,
)

# =========================
# NLP init
# =========================

_segmenter = Segmenter()
_morph_vocab = MorphVocab()
_emb = NewsEmbedding()
_morph_tagger = NewsMorphTagger(_emb)
_ner_tagger = NewsNERTagger(_emb)

# =========================
# Constants
# =========================

RESULT_TEMPLATE = {
    "Победитель": None,
    "Другие участники": None,
    "Ячейки": None,
    "Кол-во ячеек": None,
    "Типовой проект": None,
    "Проектировщик": None,
    "Дата исполнения договора": None,
    "Филиал/РЭС": None,
}

ORG_HEAD_RE = r"(?:ООО|АО|ПАО|ЗАО|ИП|ОАО|НАО)"
ORG_PATTERN = rf"{ORG_HEAD_RE}\s+[«\"][^»\"\n]+(?:[»\"])?(?:\s*\([^)]*\))?"

WINNER_CUES = [
    "победитель",
    "победителем признан",
    "признать победителем",
    "победитель закупки",
    "заключить договор с",
    "договор заключается с",
    "признано лучшим",
    "занял первое место",
]

DESIGNER_CUES = [
    "проектировщик",
    "проектная организация",
    "разработчик проекта",
    "разработчик",
    "автор проекта",
]

TYP_PROJECT_CUES = [
    "типовой проект",
    "проект",
    "марка проекта",
    "бктп",
    "ктп",
]

# =========================
# Data structures
# =========================

@dataclass
class Candidate:
    value: str
    score: float
    source: str
    evidence: str


# =========================
# Base utils
# =========================

def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\xa0", " ")
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    text = text.replace("“", '"').replace("”", '"')

    # убираем timestamp-префиксы из логов
    text = re.sub(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\s*",
        "",
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n[ \t]*\n+", "\n", text)
    return text.strip()

def extract_org_from_rank_line(line: str) -> Optional[str]:
    line = normalize_value(line)
    if not line:
        return None

    # убираем номер места в начале: "1 ...", "2 ..."
    line = re.sub(r"^\d+\s+", "", line).strip()

    # убираем служебную пометку
    if line.lower() in {"коллективный участник:", "коллективный участник"}:
        return None

    # берем организацию с адресным блоком в первой скобке
    m = re.match(
        rf"^({ORG_HEAD_RE}\s+[«\"].+?[»\"](?:\s*\([^)]*\))?(?:\s*\((?:Лидер КУ|Член КУ)\))?)",
        line,
        flags=re.IGNORECASE,
    )
    if m:
        val = cleanup_org(m.group(1))
        if val:
            return val

    # запасной вариант: берем просто название юрлица до таба / двойных пробелов / цены
    m = re.match(
        rf"^({ORG_HEAD_RE}\s+[«\"].+?[»\"])",
        line,
        flags=re.IGNORECASE,
    )
    if m:
        val = cleanup_org(m.group(1))
        if val:
            return val

    # еще один запасной вариант через regex_extract_orgs
    orgs = regex_extract_orgs(line)
    if orgs:
        return orgs[0]

    return None

def normalize_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value)
    value = re.sub(r"[ \t]+", " ", value).strip(" \n\t:;,-")
    return value or None


def normalize_quotes(text: str) -> str:
    if not text:
        return text

    # приводим все кавычки к обычным двойным
    return (
        text.replace("«", '"')
            .replace("»", '"')
            .replace("“", '"')
            .replace("”", '"')
            .replace("„", '"')
            .replace("‟", '"')
    )


def cleanup_org(name: Optional[str], keep_address: bool = False) -> Optional[str]:
    name = normalize_value(name)
    if not name:
        return None

    name = re.sub(r"\s+", " ", name).strip()
    name = normalize_quotes(name)

    if not keep_address:
        name = re.sub(r"\s*\([^)]*\)", "", name).strip()

    name = re.split(
        r"(?:,\s*ИНН\b|,\s*ОГРН\b|;\s*|,\s*адрес\b)",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()

    m = re.match(rf"^({ORG_HEAD_RE})\s+(.+)$", name, flags=re.IGNORECASE)
    if m:
        org_form = m.group(1)
        org_name = m.group(2).replace('"', '').strip()
        name = f'{org_form} "{org_name}"'

    return name or None

def unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def split_lines(text: str) -> List[str]:
    return [x.strip() for x in text.splitlines() if x.strip()]


def sentenize_text(text: str) -> List[str]:
    parts = re.split(r"(?<=[\.\!\?;])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def add_candidate(
    store: List[Candidate],
    value: Optional[str],
    score: float,
    source: str,
    evidence: str,
) -> None:
    value = normalize_value(value)
    if not value:
        return
    store.append(Candidate(value=value, score=score, source=source, evidence=evidence))


def pick_best(candidates: List[Candidate], min_score: float = 1.0) -> Optional[str]:
    if not candidates:
        return None

    merged: Dict[str, float] = {}
    for c in candidates:
        merged[c.value] = merged.get(c.value, 0.0) + c.score

    best_value, best_score = sorted(
        merged.items(),
        key=lambda x: (-x[1], len(x[0])),
    )[0]

    if best_score < min_score:
        return None
    return best_value


# =========================
# NLP helpers
# =========================

def natasha_extract_orgs(text: str) -> List[str]:
    text = clean_text(text)
    if not text:
        return []

    doc = Doc(text)
    doc.segment(_segmenter)
    doc.tag_morph(_morph_tagger)
    doc.tag_ner(_ner_tagger)

    result = []

    for span in doc.spans:
        if span.type != "ORG":
            continue

        span.normalize(_morph_vocab)
        raw = span.text.strip()
        norm = cleanup_org(raw)

        if norm:
            result.append(norm)

    return unique_keep_order(result)


def regex_extract_orgs(text: str) -> List[str]:
    if not text:
        return []

    found: List[str] = []

    for line in split_lines(text):
        line = normalize_value(line)
        if not line:
            continue

        # 1. если строка начинается с организации — берем до первого адресного блока
        m = re.match(
            rf"^\s*({ORG_HEAD_RE}\s+.*?)(?=\s*\(\d{{6}}|\s*\([^)]+\)\s*\([^)]+\)|$)",
            line,
            flags=re.IGNORECASE,
        )
        if m:
            val = cleanup_org(m.group(1))
            if val:
                found.append(val)

        # 2. fallback: берем все вхождения от юрформы до первой скобки
        for m in re.finditer(
            rf"({ORG_HEAD_RE}\s+.*?)(?=\s*\(|$)",
            line,
            flags=re.IGNORECASE,
        ):
            val = cleanup_org(m.group(1))
            if val:
                found.append(val)

    return unique_keep_order(found)


def extract_orgs_from_lines(text: str) -> List[str]:
    if not text:
        return []

    result: List[str] = []

    for line in split_lines(text):
        line = normalize_value(line)
        if not line:
            continue

        if re.match(rf"^\s*{ORG_HEAD_RE}\b", line, flags=re.IGNORECASE):
            org = cleanup_org(line)
            if org:
                result.append(org)
                continue

        orgs = regex_extract_orgs(line)
        if orgs:
            result.extend(orgs)

    return unique_keep_order(result)


def extract_organizations(text: str) -> List[str]:
    orgs = []
    orgs.extend(regex_extract_orgs(text))
    orgs.extend(natasha_extract_orgs(text))

    cleaned = []
    for org in unique_keep_order(orgs):
        if re.search(ORG_HEAD_RE, org, flags=re.IGNORECASE):
            cleaned.append(org)

    if cleaned:
        return unique_keep_order(cleaned)

    return unique_keep_order(orgs)


def normalize_date_value(value: str) -> Optional[str]:
    value = normalize_value(value)
    if not value:
        return None

    m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$", value)
    if m:
        day, month, year = m.groups()
        if len(year) == 2:
            year = "20" + year
        return f"{int(day):02d}/{int(month):02d}/{int(year):04d}"

    m = re.match(r"(\d{1,2})\s+([А-Яа-яЁё]+)\s+(\d{4})$", value, flags=re.IGNORECASE)
    if m:
        day, month_word, year = m.groups()
        months = {
            "января": "01",
            "февраля": "02",
            "марта": "03",
            "апреля": "04",
            "мая": "05",
            "июня": "06",
            "июля": "07",
            "августа": "08",
            "сентября": "09",
            "октября": "10",
            "ноября": "11",
            "декабря": "12",
        }
        month = months.get(month_word.lower())
        if month:
            return f"{int(day):02d}/{month}/{year}"

    return None


def search_dates_ru(text: str) -> List[str]:
    text = clean_text(text)
    if not text:
        return []

    out = []

    for m in re.findall(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", text):
        dt = normalize_date_value(m)
        if dt:
            out.append(dt)

    found = search_dates(text, languages=["ru"])
    if found:
        for raw, dt in found:
            if not raw or len(raw.strip()) < 4:
                continue
            out.append(dt.strftime("%d/%m/%Y"))

    return unique_keep_order(out)


# =========================
# Context extraction
# =========================

def context_windows(text: str, cues: List[str], window: int = 180) -> List[str]:
    text_low = text.lower()
    out = []

    for cue in cues:
        start = 0
        cue_low = cue.lower()
        while True:
            idx = text_low.find(cue_low, start)
            if idx == -1:
                break
            s = max(0, idx - window)
            e = min(len(text), idx + len(cue) + window)
            out.append(text[s:e].strip())
            start = idx + len(cue_low)

    return unique_keep_order(out)


def extract_between(text: str, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if m:
            val = normalize_value(m.group(1))
            if val:
                return val
    return None


def extract_execution_date_from_header_table(text: str) -> Optional[str]:
    text = clean_text(text)
    if not text:
        return None

    patterns = [
        r"Начальная цена закупки\s*Сроки выполнения работ\s*.*?С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
        r"Начальная цена закупки\s*Сроки выполнения работ\s*.*?С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}\s+[А-Яа-яЁё]+\s+\d{4})",
        r"Сроки выполнения работ\s*.*?С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
        r"Сроки выполнения работ\s*.*?С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}\s+[А-Яа-яЁё]+\s+\d{4})",
        r"С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}[./-][0-9]{1,2}[./-][0-9]{2,4})",
        r"С даты подписания договора\s*[-–—]?\s*по\s*([0-9]{1,2}\s+[А-Яа-яЁё]+\s+\d{4})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if not m:
            continue

        dt = normalize_date_value(m.group(1))
        if dt:
            return dt

    return None


def extract_branch_from_procurement_text(text: str) -> Optional[str]:
    text = clean_text(text)
    if not text:
        return None

    patterns = [
        r"для нужд\s+(.+?)\s*[-–—]\s*филиала\s+ПАО",
        r"для нужд\s+(.+?)\s*[-–—]\s*филиалу\s+ПАО",
        r"\b([А-ЯЁA-Z0-9][А-ЯЁA-Z0-9 \-/]{0,50}?)\s*[-–—]\s*филиалу\s+ПАО",
        r"\b([А-ЯЁA-Z0-9][А-ЯЁA-Z0-9 \-/]{0,50}?)\s*[-–—]\s*филиала\s+ПАО",
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
            value = normalize_value(m.group(1))
            if not value:
                continue

            value = re.sub(r"\s+", " ", value).strip(" -–—.;,")
            if len(value) <= 80:
                return value

    return None


# =========================
# Participant extraction from ranking block
# =========================

def extract_rank_block(text: str) -> Optional[str]:
    return extract_between(text, [
        r"IV\.\s*РЕШИЛИ\s*:\s*.*?ранжировать заявки .*? следующим образом:\s*(.*?)\s*Наивысшее место получает",
        r"IV\.\s*РЕШИЛИ\s*:\s*.*?ранжировать заявки .*? следующим образом:\s*(.*?)\s*Признать Победителем",
        r"IV\.\s*РЕШИЛИ\s*:\s*.*?ранжировать допущенные заявки .*? следующим образом:\s*(.*?)\s*Наивысшее место получает",
        r"IV\.\s*РЕШИЛИ\s*:\s*.*?ранжировать допущенные заявки .*? следующим образом:\s*(.*?)\s*Признать Победителем",
        r"Ранжировать .*? следующим образом:\s*(.*?)\s*Наивысшее место получает",
        r"Ранжировать .*? следующим образом:\s*(.*?)\s*Признать Победителем",
        r"Место в ранжире\s*(.*?)\s*Наивысшее место получает",
        r"Место в ранжире\s*(.*?)\s*Признать Победителем",
    ])


def _is_money_line(line: str) -> bool:
    line = line.replace("\xa0", " ")
    return bool(re.fullmatch(r"[\d\s]+,\d{2}", line.strip()))


def _is_service_rank_line(line: str) -> bool:
    low = normalize_value(line.lower() if line else "")
    if not low:
        return True

    pure_service_patterns = [
        "место в ранжире",
        "наименование участника",
        "и его адрес",
        "стоимость заявки",
        "цена заявки после переторжки",
        "сроки выполнения работ",
        "условия оплаты",
        "руб. с ндс",
    ]

    if any(p in low for p in pure_service_patterns):
        return True

    if low in {"коллективный участник:", "коллективный участник"}:
        return True

    if _is_money_line(line):
        return True

    # если строка начинается с юрлица, это НЕ служебная строка,
    # даже если в хвосте есть "не участвовали..." и т.п.
    if re.match(rf"^\s*(?:\d+\s+)?{ORG_HEAD_RE}\b", line, flags=re.IGNORECASE):
        return False

    # отдельно разрешаем строки, где есть организация не в самом начале
    if re.search(rf"\b{ORG_HEAD_RE}\b", line, flags=re.IGNORECASE):
        return False

    # вот такие строки можно отфильтровать
    if "не участвовали в переторжке" in low:
        return True
    if "в соответствии с требованиями тз" in low:
        return True

    return False


def _extract_chunk_orgs_preserving_order(chunk_lines: List[str]) -> List[str]:
    result: List[str] = []

    for line in chunk_lines:
        line = normalize_value(line)
        if not line:
            continue

        org = extract_org_from_rank_line(line)
        if org:
            result.append(org)
            continue

        for found in regex_extract_orgs(line):
            if found:
                result.append(found)

    return unique_keep_order(result)


def extract_ranked_participants(text: str) -> List[str]:
    text = clean_text(text)
    if not text:
        return []

    rank_block = extract_rank_block(text)
    if not rank_block:
        m = re.search(
            r"Место в ранжире.*?(?=(?:Наивысшее место получает|Признать Победителем|$))",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return []
        rank_block = m.group(0)

    lines = split_lines(rank_block)
    participants: List[str] = []

    current_chunk: List[str] = []
    current_rank_started = False

    for line in lines:
        line = normalize_value(line)
        if not line:
            continue

        # новая строка ранга: "1 ООО ..." или "2 Коллективный участник:"
        if re.match(r"^\d+\s+", line):
            if current_chunk:
                participants.extend(_extract_chunk_orgs_preserving_order(current_chunk))
                current_chunk = []

            current_rank_started = True
            current_chunk.append(line)
            continue

        # отдельная строка с номером места
        if re.fullmatch(r"\d+", line):
            if current_chunk:
                participants.extend(_extract_chunk_orgs_preserving_order(current_chunk))
                current_chunk = []
            current_rank_started = True
            continue

        if not current_rank_started:
            continue

        # служебные строки без организаций пропускаем
        if _is_service_rank_line(line) and not re.search(rf"\b{ORG_HEAD_RE}\b", line, flags=re.IGNORECASE):
            continue

        current_chunk.append(line)

    if current_chunk:
        participants.extend(_extract_chunk_orgs_preserving_order(current_chunk))

    return unique_keep_order(participants)


# =========================
# Field extractors
# =========================

def extract_winner_candidates(text: str) -> List[Candidate]:
    candidates: List[Candidate] = []
    lines = split_lines(text)

    patterns = [
        rf"признать\s+победителем.*?\s+({ORG_PATTERN})",
        rf"заключить\s+договор\s+с\s+({ORG_PATTERN})",
        rf"победителем\s+признан[а-я]*\s+({ORG_PATTERN})",
        rf"выигравш[а-я]+\s+организац[а-я]+\s*[-: ]+\s*({ORG_PATTERN})",
        rf"первое\s+место.*?({ORG_PATTERN})",
    ]
    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE):
            add_candidate(candidates, cleanup_org(m.group(1)), 8.0, "winner_regex", m.group(0))

    for chunk in context_windows(text, WINNER_CUES, window=200):
        orgs = extract_organizations(chunk)
        for idx, org in enumerate(orgs):
            score = 6.0 - min(idx, 3) * 1.0
            add_candidate(candidates, org, score, "winner_context", chunk)

    rank_patterns = [
        rf"место.*?\n\s*1[\t ]+({ORG_PATTERN})(?:[\t ]+|\n|$)",
        rf"наименование.*?\n\s*1[\t ]+({ORG_PATTERN})(?:[\t ]+|\n|$)",
    ]
    for p in rank_patterns:
        m = re.search(p, text, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        if m:
            add_candidate(candidates, cleanup_org(m.group(1)), 7.0, "winner_rank_block", m.group(0))

    for line in lines:
        m = re.match(rf"^\s*1[\t ]+({ORG_PATTERN})(?:[\t ]+|$)", line, flags=re.IGNORECASE)
        if m:
            add_candidate(candidates, cleanup_org(m.group(1)), 6.5, "winner_rank_line", line)

        cols = [c.strip() for c in line.split("\t") if c.strip()]
        if len(cols) >= 2 and cols[0] == "1":
            orgs = extract_organizations(cols[1])
            for org in orgs:
                add_candidate(candidates, org, 6.0, "winner_rank_cols", line)

    return candidates


def extract_participants(text: str) -> List[str]:
    return extract_ranked_participants(text)


def extract_designer_candidates(text: str) -> List[Candidate]:
    candidates: List[Candidate] = []
    lines = split_lines(text)

    patterns = [
        r"проектировщик\s*[:\-]\s*(.+)",
        r"проектная организация\s*[:\-]\s*(.+)",
        r"разработчик проекта\s*[:\-]\s*(.+)",
        r"разработчик\s*[:\-]\s*(.+)",
        r"автор проекта\s*[:\-]\s*(.+)",
    ]

    for line in lines:
        for p in patterns:
            m = re.search(p, line, flags=re.IGNORECASE)
            if not m:
                continue

            tail = normalize_value(m.group(1))
            if not tail:
                continue

            orgs = extract_organizations(tail)
            if orgs:
                for org in orgs:
                    add_candidate(candidates, org, 7.0, "designer_regex_org", line)
            else:
                add_candidate(candidates, tail, 5.0, "designer_regex_text", line)

    for chunk in context_windows(text, DESIGNER_CUES, window=180):
        orgs = extract_organizations(chunk)
        if orgs:
            for idx, org in enumerate(orgs):
                add_candidate(candidates, org, 4.5 - idx * 0.5, "designer_context_org", chunk)
        else:
            for cue in DESIGNER_CUES:
                m = re.search(rf"{re.escape(cue)}\s*[:\-]?\s*(.+)", chunk, flags=re.IGNORECASE)
                if m:
                    add_candidate(candidates, normalize_value(m.group(1)), 3.5, "designer_context_text", chunk)

    return candidates


def extract_execution_date_candidates(text: str) -> List[Candidate]:
    candidates: List[Candidate] = []

    header_date = extract_execution_date_from_header_table(text)
    if header_date:
        add_candidate(
            candidates,
            header_date,
            10.0,
            "date_header_table",
            "Начальная цена закупки / Сроки выполнения работ",
        )

    return candidates


def extract_branch_candidates(text: str) -> List[Candidate]:
    candidates: List[Candidate] = []

    branch = extract_branch_from_procurement_text(text)
    if branch:
        add_candidate(
            candidates,
            branch,
            10.0,
            "branch_procurement_text",
            "branch from procurement text",
        )

    return candidates


def extract_typ_project_candidates(text: str) -> List[Candidate]:
    candidates: List[Candidate] = []

    patterns = [
        r"(БКТП-\d+/\d+,\d+\s*кВ\s+с\s+тр-ми\s*[\dхxX]+\s*кВА)",
        r"(БКТП-\d+/\d+,\d+\s*кВ)",
        r"(КТП-\d+/\d+,\d+\s*кВ\s+с\s+тр-ми\s*[\dхxX]+\s*кВА)",
        r"(КТП-\d+/\d+,\d+\s*кВ)",
        r"(ТП-\d+/\d+,\d+\s*кВ)",
    ]

    for p in patterns:
        for m in re.finditer(p, text, flags=re.IGNORECASE):
            add_candidate(candidates, normalize_value(m.group(1)), 6.0, "typ_project_regex", m.group(0))

    for chunk in context_windows(text, TYP_PROJECT_CUES, window=150):
        for p in patterns:
            for m in re.finditer(p, chunk, flags=re.IGNORECASE):
                add_candidate(candidates, normalize_value(m.group(1)), 4.0, "typ_project_context", chunk)

    return candidates


def extract_cells_unique(text: str) -> Tuple[Optional[str], Optional[str]]:
    patterns = [
        r"\bяч\.\s*(\d+)\b",
        r"\bяч\.\s*№?\s*(\d+)\b",
        r"\bячейк[аи]?\s*№?\s*(\d+)\b",
    ]

    nums = []
    for p in patterns:
        nums.extend(re.findall(p, text, flags=re.IGNORECASE))

    unique = unique_keep_order(nums)
    if not unique:
        return None, None

    return "; ".join(f"яч.{n}" for n in unique), str(len(unique))


# =========================
# Main API
# =========================

def extract_tender_fields(
    text: str,
    fields_to_extract: Optional[List[str]] = None,
) -> Dict[str, Optional[str]]:
    text = clean_text(text)
    result = RESULT_TEMPLATE.copy()

    if fields_to_extract is None:
        fields_to_extract = list(RESULT_TEMPLATE.keys())

    if "Победитель" in fields_to_extract:
        result["Победитель"] = pick_best(extract_winner_candidates(text), min_score=4.0)

    if "Другие участники" in fields_to_extract:
        participants = extract_participants(text)
        if participants:
            winner = result.get("Победитель")
            others = [p for p in participants if p != winner]
            others = unique_keep_order(others)
            if others:
                result["Другие участники"] = "; ".join(others)

    if "Дата исполнения договора" in fields_to_extract:
        result["Дата исполнения договора"] = pick_best(
            extract_execution_date_candidates(text),
            min_score=4.0,
        )

    if "Филиал/РЭС" in fields_to_extract:
        result["Филиал/РЭС"] = pick_best(
            extract_branch_candidates(text),
            min_score=3.0,
        )

    if "Ячейки" in fields_to_extract or "Кол-во ячеек" in fields_to_extract:
        cells, cells_count = extract_cells_unique(text)
        if "Ячейки" in fields_to_extract:
            result["Ячейки"] = cells
        if "Кол-во ячеек" in fields_to_extract:
            result["Кол-во ячеек"] = cells_count

    if "Типовой проект" in fields_to_extract:
        result["Типовой проект"] = pick_best(
            extract_typ_project_candidates(text),
            min_score=3.0,
        )

    if "Проектировщик" in fields_to_extract:
        result["Проектировщик"] = pick_best(
            extract_designer_candidates(text),
            min_score=3.0,
        )

    return result