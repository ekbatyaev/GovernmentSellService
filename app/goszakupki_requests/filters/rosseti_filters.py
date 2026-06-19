import re

# Фильтры в формате регулярных выражений

FILTERS_CUSTOMER_ROSSETI = [
    # Образец (уже был)
    r"\b(?:ПАО\s+)?Россети\s+Московск(?:ий|ого|ому|им|ом)?\s+регион(?:а|у|ом|е)?\b",

    # ПАО "Россети Центр и Приволжье"
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Мариэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Нижновэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Кировэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Удмуртэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Владимирэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Ивэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Рязаньэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Тулаэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+и\s+Приволжье\s+)?Калугаэнерго\b",

    # ПАО "Россети Волга"
    r"\b(?:ПАО\s+)?Россети\s+(?:Волга\s+)?Оренбургэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Волга\s+)?Самарские\s+распределительные\s+сети\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Волга\s+)?Саратовские\s+распределительные\s+сети\b",

    # ПАО "Россети Центр"
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Воронежэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Белгородэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Орелэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Костромаэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Ярэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Тверьэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Смоленскэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Брянскэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Курскэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Липецкэнерго\b",
    r"\b(?:ПАО\s+)?Россети\s+(?:Центр\s+)?Тамбовэнерго\b",
]

FILTERS_JOB_NAME_ROSSETI = [
    r"РТП-10/0,4\s*кВ",
    r"ТП-10/0,4\s*кВ",
    r"РП\s*-?\s*10\s*кВ",
    r"РП\s*-?\s*20\s*кВ",
    r"БКТП\s*-?\s*(?:10|20)?/?0?,?4?\s*кВ?",
    r"КТП\s*-?\s*\d*[-/]?(?:10|6)?/?0?,?4?\s*кВ?",
    r"строительств[а-я]*\s+РТП",
    r"строительств[а-я]*\s+РП",
    r"строительств[а-я]*\s+ТП",
    r"строительств[а-я]*\s+БКТП",
    r"строительств[а-я]*\s+КТП",
    r"реконструкци[а-я]*\s+ТП",
    r"реконструкци[а-я]*\s+РП",
    r"реконструкци[а-я]*\s+РТП",
    r"реконструкци[а-я]*\s+БКТП",
    r"реконструкци[а-я]*\s+КТП",
    r"модернизаци[а-я]*\s+РП",
    r"проектно\s*[-–—]?\s*изыскательск[а-я]*\s+работ[а-я]*",
    r"ПИР",
    r"СМР",
    r"ПНР",
    r"право\s+заключени[а-я]*\s+рамочн[а-я]*\s+соглашени[а-я]*",
    r"определени[а-я]*\s+поставщик[а-я]*\s+на\s+поставк[а-я]*",
    r"замен[а-я]*\s+оборудовани[а-я]*",
    r"проектировани[а-я]*\s+сет[а-я]*",
    r"для нужд МКС",
    r"РТП-20/0,4\s*кВ",
    r"ТП-20/0,4\s*кВ",
]

FILTERS_JOB_EXCLUDE_HARD_ROSSETI = [
    r"\bавто(?:мобил[а-я]*|транспорт[а-я]*|техник[а-я]*|шин[а-я]*|запчаст[а-я]*)\b",
    r"бензоинструмента",
    r"переустройств[а-я]*",
    r"кабельн[а-я]*\s+исполнени[а-я]*",
    r"воздушн[а-я]*\s+участк[а-я]*"
]

FILTERS_LINE_ONLY_ACTION_ROSSETI= [
    r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
    r"(?:\d+\s*)?(?:КЛ|РКЛ|ВЛ|ВЛЗ|КВЛ|ЛЭП)\s*-?\s*\d+(?:\s*[,/]\s*\d+)?\s*кВ\b"
]


FILTERS_TARGET_OBJECT_ACTION_ROSSETI = [
    r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
    r"(?:нов[а-я]*\s+|встроенн[а-я]*\s+|выносн[а-я]*\s+)?"
    r"(?:\d+\s*)?"
    r"(?:РТП|БКТП|КТП|РП|ТП|РЩ)"
    r"\s*-?\s*"
    r"(?:№\s*\d+[А-ЯA-Zа-яa-z]?\s*)?"
    r"(?:\d+\s*/\s*0\s*,?\s*4|\d+)?"
    r"\s*(?:кВ)?\b"
]

FILTERS_JOB_EXCLUDE_SOFT_ROSSETI = [
    r"\bПС(?:-\s*|\s+)(?:110|220|500)(?:/\d+)*\s*кВ\b"
]

TARGET_OBJECT_PATTERNS_ROSSETI = [
    r"\bТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРП\s*-?\s*(?:6|10|20)\s*(?:кВ)?\b",
    r"\bБКТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bКТП\s*-?\s*\d*(?:[-/]\s*(?:6|10|20))?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
]

# Компиляция фильтров

FILTERS_PATTERNS_ROSSETI = [re.compile(p, re.IGNORECASE) for p in FILTERS_CUSTOMER_ROSSETI]

JOB_PATTERNS_ROSSETI = [re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_NAME_ROSSETI]

JOB_EXCLUDE_HARD_PATTERNS_ROSSETI = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_HARD_ROSSETI
]

LINE_ONLY_ACTION_PATTERNS_ROSSETI = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_LINE_ONLY_ACTION_ROSSETI
]

TARGET_OBJECT_ACTION_PATTERNS_ROSSETI = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_TARGET_OBJECT_ACTION_ROSSETI
]

JOB_EXCLUDE_SOFT_PATTERNS_ROSSETI = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_SOFT_ROSSETI
]
TARGET_PATTERNS_ROSSETI = [re.compile(p, re.IGNORECASE) for p in TARGET_OBJECT_PATTERNS_ROSSETI]

# Функция фильтрация

def request_filters_rosseti(customer_name, work_name)-> bool:

    ok_customer = any(p.search(customer_name) for p in FILTERS_PATTERNS_ROSSETI)
    excluded_hard = any(p.search(work_name) for p in JOB_EXCLUDE_HARD_PATTERNS_ROSSETI)
    excluded_soft = any(p.search(work_name) for p in JOB_EXCLUDE_SOFT_PATTERNS_ROSSETI)

    ok_job_raw = any(p.search(work_name) for p in JOB_PATTERNS_ROSSETI)

    title_part = work_name

    m_title = re.search(r"по\s+титулу\s*:\s*(.+)", title_part, re.IGNORECASE)
    if m_title:
        title_part = m_title.group(1)

    title_part = re.split(
        r",\s*в\s+т\.?\s*ч\.?|;\s*в\s+т\.?\s*ч\.?|для\s+нужд|г\.\s*Москва|МО,",
        title_part,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0]

    has_line_only_action = any(
        p.search(title_part) for p in LINE_ONLY_ACTION_PATTERNS_ROSSETI
    )

    has_target_object_action = any(
        p.search(title_part) for p in TARGET_OBJECT_ACTION_PATTERNS_ROSSETI
    )

    is_line_only_work = has_line_only_action and not has_target_object_action

    has_group_objects = bool(
        re.search(
            r"(?:по\s+[А-ЯЁа-яё\-]+(?:ому|ему)\s+району|по\s+приказу|по\s+распоряжени[а-я]*|по\s+программ[а-я]*)"
            r".{0,250}"
            r"\(\s*\d+\s+объект",
            work_name,
            re.IGNORECASE
        )
    )

    has_metering = bool(
        re.search(
            r"установк[а-я]*\s+прибор[а-я]*",
            work_name,
            re.IGNORECASE
        )
    )

    has_electro_supply = bool(
        re.search(
            r"поставк[а-я]*.*(?:коммутационн[а-я]*|электромонтажн[а-я]*|"
            r"электроустановочн[а-я]*|электроизоляционн[а-я]*|"
            r"светотехническ[а-я]*|электротехническ[а-я]*|электронн[а-я]*|"
            r"фонар[а-я]*|запасн[а-я]*\s+част[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    has_tech_connection = bool(
        re.search(
            r"(техническ[а-я]*\s+услови[а-я]*|технологическ[а-я]*\s+присоединени[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    has_rosseti_context = bool(
        re.search(
            r"(Россети)",
            work_name,
            re.IGNORECASE
        )
    )

    has_zes_order_objects = bool(
        re.search(
            r"по\s+объектам\s+ЗЭС\s+распоряжени[а-я]*",
            work_name,
            re.IGNORECASE
        )
    )

    has_bktp_in_tu = bool(
        re.search(
            r"(техническ[а-я]*\s+услови[а-я]*|п\.\s*11).{0,120}\b\d*\s*БКТП\b",
            work_name,
            re.IGNORECASE
        )
    )

    has_pir_by_titles = bool(
        re.search(
            r"\bПИР\b.{0,80}\bпо\s+(?:\d+|одному|двум|тр[её]м|четыр[её]м|пяти|шести|семи|восьми|девяти|десяти)\s+титул[а-я]*",
            work_name,
            re.IGNORECASE
        )
    )

    has_tp_contract_pir = bool(
        re.search(
            r"\bПИР\b.{0,80}\bпо\s+договор[а-я]*\s+ТП\b",
            work_name,
            re.IGNORECASE
        )
    )

    ok_job = ok_job_raw and (
            has_target_object_action
            or has_group_objects
            or has_metering
            or has_electro_supply
            or has_zes_order_objects
            or has_bktp_in_tu
            or has_pir_by_titles
            or has_tp_contract_pir
            or (has_tech_connection and has_rosseti_context)
    )

    has_from = bool(
        re.search(r"\b(от|сооружаемой)\s+(ТП|ячейк[а-я]|РТП|РП|БКТП|КТП)\b", work_name, re.IGNORECASE)
    )

    is_land_release_line_work = bool(
        re.search(
            r"для\s+освобождени[а-я]*\s+земельн[а-я]*\s+участк[а-я]*",
            work_name,
            re.IGNORECASE
        )
        and re.search(
            r"\b(?:КВЛ|КЛ|ВЛЗ|ВЛ)\s*-?\s*\d+(?:\s*,\s*\d+)?\s*кВ\b",
            work_name,
            re.IGNORECASE
        )
        and not re.search(
            r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
            r"(?:ТП|РТП|РП|БКТП|КТП)\b",
            work_name,
            re.IGNORECASE
        )
    )

    object_pattern = r"(?<![А-Яа-яA-Za-z])(РТП|БКТП|КТП|РП|ТП)(?![А-Яа-яA-Za-z])"

    from_to_pattern = (
        r"\bот\b.*?\bдо\b.*?"
        r"(?=,\s*(?:\d+\s*КЛ|\d+КЛ|в\s+т\.ч\.|ПИР\b|г\.\s|для\s+нужд\b)|$)"
    )

    from_to_ranges = [
        match.span()
        for match in re.finditer(
            from_to_pattern,
            work_name,
            re.IGNORECASE
        )
    ]

    has_without_from = any(
        not any(start <= match.start() < end for start, end in from_to_ranges)
        and not re.search(
            r"сооружаемой\s*$",
            work_name[:match.start()],
            re.IGNORECASE
        )
        for match in re.finditer(
            object_pattern,
            work_name,
            re.IGNORECASE
        )
    )

    only_source_object = has_from and not has_without_from

    source_object_allowed = bool(
        re.search(
            r"(для\s+нужд\s+МКС|ПИР|СМР|ПНР|строительств[а-я]*|технологическ[а-я]*\s+присоединени[а-я]*)",
            work_name,
            re.IGNORECASE
        )
    )

    excluded_job = (
            excluded_hard
            or is_land_release_line_work
            or is_line_only_work
            or (excluded_soft and not has_target_object_action)
            or (only_source_object and not source_object_allowed)
    )

    if ok_customer and ok_job and not excluded_job:
        return True
    return False
