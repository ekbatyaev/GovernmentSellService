
def normalize_for_title_check(text: str) -> str:
    text = (text or "").replace(" ", " ").replace("Ё", "Е").replace("ё", "е")
    return re.sub(r"\s+", " ", text).strip().lower()


def is_working_documentation_title_page(text: str) -> bool:
    """Титульный лист рабочей документации. Основной маркер: 'РАБОЧАЯ ДОКУМЕНТАЦИЯ'."""
    normalized = normalize_for_title_check(text)
    return bool(normalized) and bool(re.search(r"рабочая\s+документация", normalized))

def check_availability_of_fields_from_text(text: str) -> str:
    """
    Ищет признаки ПЧ/УПП/ШУ и т.п. Корни слов, чтобы покрыть падежи и числа.
    """
    pattern = r"(ПЧ|ЧП|УПП|SCADA|ШУ|преобразоват.*частот|устройств.*плавн.*пуск|шкаф.*управл)"
    return "Есть" if re.search(pattern, text, re.IGNORECASE) else "Нету"

def extract_designer_from_title_text(text: str) -> str:
    """Достаёт проектировщика с титульного листа. Если явного кандидата нет — ''."""
    if not text or not text.strip():
        return ""

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in text.replace(" ", " ").splitlines()
        if line and line.strip()
    ]
    candidates = []

    for source_text in ("\n".join(lines), " ".join(lines)):
        for pattern in _DESIGNER_PATTERNS:
            for match in re.finditer(pattern, source_text, flags=re.IGNORECASE | re.MULTILINE):
                candidates.append(normalize_designer_name(match.group(1)))

    # Правовая форма и название на соседних строках.
    for i, line in enumerate(lines):
        if re.fullmatch(r"Общество\s+с\s+Ограниченной\s+Ответственностью", line, flags=re.IGNORECASE):
            if i + 1 < len(lines) and lines[i + 1]:
                candidates.append(normalize_designer_name(f"{line} {lines[i + 1]}"))

    # ООО/АО/ПАО без кавычек в шапке титульника.
    for line in lines[:8]:
        if re.match(r"^(ООО|АО|ПАО)\b", line, flags=re.IGNORECASE):
            candidates.append(normalize_designer_name(line))

    cleaned, seen = [], set()
    for candidate in candidates:
        candidate = normalize_designer_name(candidate)
        lower = candidate.lower()

        if len(candidate) < 5 or lower in seen:
            continue
        if any(word in lower for word in _DESIGNER_STOP_WORDS):
            continue
        if not _DESIGNER_LEGAL_FORM_RE.search(candidate):
            continue

        cleaned.append(candidate)
        seen.add(lower)

    return max(cleaned, key=len) if cleaned else ""