import re
from typing import Union, Dict, Any

# Фильтры для ITCLG сектора

TARGET_CODES_ITCLG = [
    "28.25.13.110",
    "28.25.13.130",
    "28.25.14.110",
    "28.25.11.110",
    "26.20.40.110",
    "43.22.12.120",
    "33.12.18.000",
]

FILTERS_COMPONENTS_ITCLG = [
    # Группа А: Типы кондиционеров

    r"\bпрецизион[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bпрецизион[а-яё]*\s+охлажден[а-яё]*\b",
    r"\bвнутриряд[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bмежряд[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bвнутристоеч[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bшкафн[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bпериметраль[а-яё]*\s+кондиционер[а-яё]*\b",
    r"\bкондиционер[а-яё]*\s+шкафного\s+типа\b",

    # Группа Б: Чиллеры и хладоны (Линейка CoolFlow)

    r"\bчиллер[а-яё]*\b",
    r"\bводоохлаждающ[а-яё]*\s+машин[а-яё]*\b",
    r"\bводоохладител[а-яё]*\b",
    r"\bфрикулинг[а-яё]*\b|\bсвободн[а-яё]*\s+охлажден[а-яё]*\b",
    r"\bвыносн[а-яё]*\s+конденсатор[а-яё]*\b",
    r"\bсух[а-яё]*\s+градирн[а-яё]*\b",
    r"\bдрайкулер[а-яё]*\b"
]

FILTERS_BRANDS_ITCLG = [
    # Группа Г: Поиск по бренду (Если закладывают конкретно Systeme Electric)
    r"\bsysteme\s+electric\b",
    r"\bсистэм\s+электрик\b",
    r"\bcoolflow\b",
    r"\bcoolrow\b",
    r"\bcoolroom\b",
    r"\bcoolrack\b"
]

FILTERS_WORK_ITCLG = [
    # Группа В: Локация и инфраструктура (Для контекстного поиска)

    r"\bохлажден[а-яё]*\s+цод\b",
    r"\bкондиционирован[а-яё]*\s+цод\b",
    r"\bохлажден[а-яё]*\s+серверн[а-яё]*\b",
    r"\bкондиционирован[а-яё]*\s+серверн[а-яё]*\b",
    r"\bизоляц[а-яё]*\s+горяч[а-яё]*\s+коридор[а-яё]*\b",
    r"\bизоляц[а-яё]*\s+холодн[а-яё]*\s+коридор[а-яё]*\b"
]

# Компиляция фильтров

COMPONENT_PATTERNS_ITCLG = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS_ITCLG]
BRAND_PATTERNS_ITCLG = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS_ITCLG]
FILTERS_WORK_PATTERNS_ITCLG = [re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_ITCLG]

# Функция фильтрация

def request_filters_itclg(text: str, lots: list, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка проходит любой из фильтров,
    возвращая при этом номер категории.
    """

    has_component = _matches(COMPONENT_PATTERNS_ITCLG, text)
    has_brand = _matches(BRAND_PATTERNS_ITCLG, text)

    has_work_patterns = _matches(FILTERS_WORK_PATTERNS_ITCLG, text)

    result = False

    if has_work_patterns:
        result = True
        reason = "work_match: есть маркер ИБП и признак поставки/монтажа/настройки/испытаний"

    elif has_component or has_brand:
        result = True
        reason = "brand_match: совпадение по поставке"

    elif has_okpd2_match(lots, TARGET_CODES_ITCLG):
        result = True
        reason  = "has_okpd2_match: есть совпадения по базе okpd2"

    else:
        result = False
        reason = "no_match: нет релевантных маркеров по ITCLG"

    if debug:
        return {
            "result": result,
            "reason": reason,
            "filter_name": "ITCLG",
            "component": has_component,
            "brand": has_brand,
            "work_patterns": has_work_patterns,
            "normalized_text": text,
        }

    return {"result": result, "filter_name": "ITCLG"}


# Фильтры для ITRAA сектора

TARGET_CODES_ITRAA = [
    "26.20.40.110",
    "27.33.13.130",
    "27.12.11.000",
    "26.20.40.190",
    "25.11.23.119",
    "32.99.59.000",
]

FILTERS_COMPONENTS_ITRAA = [
    # Группа А: Монтажные шкафы, стойки и конструктивы (Линейка Uniprom Rack)

    r"\bтелекоммуникацион[а-яё]*\s+шкаф[а-яё]*\b",
    r"\bсерверн[а-яё]*\s+шкаф[а-яё]*\b",
    r"\bмонтажн[а-яё]*\s+шкаф[а-яё]*\b",
    r"\bшкаф[а-яё]*\s+19\s*дюйм[а-яё]*\b|\b19\s*\"\b",
    r"\bсерверн[а-яё]*\s+стойк[а-яё]*\b",
    r"\bшкаф[а-яё]*\s+(?:42|48|52)u\b",

    # Группа Б: Распределение питания в стойках (Линейка Uniprom Rack PDU)

    r"\bбрп\b",
    r"\bpdu\b",
    r"\bблок[а-яё]*\s+распределения\s+питания\b",
    r"\b(?:вертикаль|горизонталь)[а-яё]*\s+брп\b",
    r"\bуправляем[а-яё]*\s+(?:брп|pdu)\b",
    r"\bбазов[а-яё]*\s+брп\b",
    r"\bрозеточн[а-яё]*\s+блок[а-яё]*\b",
]

FILTERS_BRANDS_ITRAA = [
    # Группа Г: Поиск по оригинальным брендам и сериям
    r"\buniprom\s+rack\b",
    r"\buniprom\s+containment\b",
    r"\buniprom\b",
    r"\bexcelente\b",
    r"\bsysteme\s+electric\b",
    r"\bсистэм\s+электрик\b",
]

FILTERS_WORK_ITRAA = [
    # Группа В: Кабель-менеджмент, аксессуары и изоляция потоков (Excelente, Uniprom Containment)

    r"\bкабельн[а-яё]*\s+организатор[а-яё]*\b",
    r"\b(?:вертикаль|горизонталь)[а-яё]*\s+организатор[а-яё]*\b",
    r"\bпластиков[а-яё]*\s+заглушк[а-яё]*\s+1u\b|\bпанель-заглушк[а-яё]*\b",
    r"\bщеточн[а-яё]*\s+уплотнител[а-яё]*\b",
    r"\bизоляц[а-яё]*\s+воздушн[а-яё]*\s+поток[а-яё]*\b",
    r"\bизоляц[а-яё]*\s+(?:горяч|холодн)[а-яё]*\s+коридор[а-яё]*\b",
    r"\bразделен[а-яё]*\s+температурн[а-яё]*\s+зон[а-яё]*\b",
]

# Компиляция фильтров

COMPONENT_PATTERNS_ITRAA = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS_ITRAA]
BRAND_PATTERNS_ITRAA = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS_ITRAA]
FILTERS_WORK_PATTERNS_ITRAA = [re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_ITRAA]

# Функция фильтрация

def request_filters_itraa(text: str, lots: list, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка проходит любой из фильтров,
    возвращая при этом номер категории.
    """

    has_component = _matches(COMPONENT_PATTERNS_ITRAA, text)
    has_brand = _matches(BRAND_PATTERNS_ITRAA, text)

    has_work_patterns = _matches(FILTERS_WORK_PATTERNS_ITRAA, text)

    result = False

    if has_work_patterns:
        result = True
        reason = "work_match: есть маркер кабель-менеджмента/изоляции воздушных потоков"

    elif has_component or has_brand:
        result = True
        reason = "brand_match: совпадение по поставке"

    elif has_okpd2_match(lots, TARGET_CODES_ITRAA):
        result = True
        reason = "has_okpd2_match: есть совпадения по базе okpd2"

    else:
        result = False
        reason = "no_match: нет релевантных маркеров по ITRAA"

    if debug:
        return {
            "result": result,
            "reason": reason,
            "filter_name": "ITRAA",
            "component": has_component,
            "brand": has_brand,
            "work_patterns": has_work_patterns,
            "normalized_text": text,
        }

    return {"result": result, "filter_name": "ITRAA"}


# Фильтры для ITDIG сектора

TARGET_CODES_ITDIG = [
    "26.51.70.190",
    "26.51.51.130",
    "58.29.29.000",
    "26.30.50.000",
    "26.51.43.120",
]

FILTERS_COMPONENTS_ITDIG = [
    # Группа А: Мониторинг микроклимата и окружающей среды (Линейка SystemeBotz)

    r"\bмониторинг[а-яё]*\s+микроклимат[а-яё]*\b",
    r"\bмониторинг[а-яё]*\s+параметр[а-яё]*\s+окружающ[а-яё]*\s+сред[а-яё]*\b",
    r"\bконтроллер[а-яё]*\s+микроклимат[а-яё]*\b",
    r"\bдатчик[а-яё]*\s+температур[а-яё]*\s+серверн[а-яё]*\b",
    r"\bдатчик[а-яё]*\s+влажност[а-яё]*\s+цод\b",
    r"\bмониторинг[а-яё]*\s+серверн[а-яё]*\s+стоек\b",

    # Группа Б: Мониторинг аккумуляторных батарей ИБП (Линейка SystemeBMU)

    r"\bмониторинг[а-яё]*\s+акб\b",
    r"\bмониторинг[а-яё]*\s+аккумулятор[а-яё]*\b",
    r"\bдатчик[а-яё]*\s+батаре[а-яё]*\b",
    r"\bконтроллер[а-яё]*\s+линейки\s+акб\b",
    r"\bизмерен[а-яё]*\s+внутрен[а-яё]*\s+сопротивлен[а-яё]*\s+батаре[а-яё]*\b",
    r"\bдатчик[а-яё]*\s+холла\s+акб\b",

    # Группа В: Контроль доступа в стойки / СКУД (Линейка SystemeBotz AC)

    r"\bконтроль[а-яё]*\s+доступ[а-яё]*\s+стойк[а-яё]*\b",
    r"\bэлектрон[а-яё]*\s+замок[а-яё]*\s+шкаф[а-яё]*\b|\bэлектрон[а-яё]*\s+замок[а-яё]*\s+стойк[а-яё]*\b",
    r"\bригельн[а-яё]*\s+механизм[а-яё]*\s+скуд\b",
    r"\bдатчик[а-яё]*\s+положен[а-яё]*\s+двер[а-яё]*\b|\bдатчик[а-яё]*\s+открыт[а-яё]*\s+двер[а-яё]*\s+шкаф[а-яё]*\b",
]

FILTERS_BRANDS_ITDIG = [
    # Группа Д: Оригинальные серии и бренды
    r"\bdc\s+guard\b",
    r"\bsystemebotz\b",
    r"\bsystemebmu\b",
    r"\bsysteme\s+electric\b",
    r"\bсистэм\s+электрик\b",
]

FILTERS_WORK_ITDIG = [
    # Группа Г: Программное обеспечение для ЦОД (DC Guard)

    r"\bцентрализован[а-яё]*\s+мониторинг[а-яё]*\s+цод\b",
    r"\bпо\s+мониторинг[а-яё]*\s+инфраструктур[а-яё]*\b",
    r"\bлицензи[а-яё]*\s+мониторинг[а-яё]*\s+серверн[а-яё]*\b",
    r"\bсистем[а-яё]*\s+мониторинг[а-яё]*\s+dcim\b|\bdcim\b",
]

# Компиляция фильтров

COMPONENT_PATTERNS_ITDIG = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS_ITDIG]
BRAND_PATTERNS_ITDIG = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS_ITDIG]
FILTERS_WORK_PATTERNS_ITDIG = [re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_ITDIG]

# Функция фильтрация

def request_filters_itdig(text: str, lots: list, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка проходит любой из фильтров,
    возвращая при этом номер категории.
    """

    has_component = _matches(COMPONENT_PATTERNS_ITDIG, text)
    has_brand = _matches(BRAND_PATTERNS_ITDIG, text)

    has_work_patterns = _matches(FILTERS_WORK_PATTERNS_ITDIG, text)

    result = False

    if has_work_patterns:
        result = True
        reason = "work_match: есть маркер ПО мониторинга/DCIM для ЦОД"

    elif has_component or has_brand:
        result = True
        reason = "brand_match: совпадение по поставке"

    elif has_okpd2_match(lots, TARGET_CODES_ITDIG):
        result = True
        reason = "has_okpd2_match: есть совпадения по базе okpd2"

    else:
        result = False
        reason = "no_match: нет релевантных маркеров по ITDIG"

    if debug:
        return {
            "result": result,
            "reason": reason,
            "filter_name": "ITDIG",
            "component": has_component,
            "brand": has_brand,
            "work_patterns": has_work_patterns,
            "normalized_text": text,
        }

    return {"result": result, "filter_name": "ITDIG"}


# Фильтры для IT3PH сектора

TARGET_CODES_IT3PH = [
    "26.20.40.110",
    "27.90.40.110",
    "27.20.22.000",
    "27.20.23.000",
    "26.12.30.000",
    "33.12.18.000",
]

FILTERS_COMPONENTS_IT3PH = [
    # Группа А: Общетехнические названия ИБП и систем питания

    r"\bибп\b",
    r"\bисточник[а-яё]*\s+бесперебойного\s+питания\b",
    r"\bисточник[а-яё]*\s+бесперебойного\s+электропитания\b",
    r"\bсистем[а-яё]*\s+бесперебойного\s+питания\b",
    r"\bгарантирован[а-яё]*\s+электроснабжен[а-яё]*\b",
    r"\bгарантирован[а-яё]*\s+электропитани[а-яё]*\b",

    # Группа Б: Конкретные типы ИБП по фазности и архитектуре

    r"\bоднофазн[а-яё]*\s+ибп\b|\bибп\s*1:1\b",
    r"\bтрехфазн[а-яё]*\s+ибп\b|\bибп\s*3:3\b",
    r"\bмодульн[а-яё]*\s+ибп\b",
    r"\bмасштабируем[а-яё]*\s+ибп\b",
    r"\bонлайн[- ]?ибп\b|\bдвойн[а-яё]*\s+преобразован[а-яё]*\b",
    r"\bлинейно-интерактив[а-яё]*\s+ибп\b",
    r"\bибп\s+в\s+стойку\b|\bибп\s+rack\b",
]

FILTERS_BRANDS_IT3PH = [
    # Группа Г: Оригинальные серии и бренды
    r"\bsmart-save\b",
    r"\bexcelente\b",
    r"\bsysteme\s+electric\b",
    r"\bсистэм\s+электрик\b",
]

FILTERS_WORK_IT3PH = [
    # Группа В: Батареи и комплектующие к ИБП

    r"\bаккумулятор[а-яё]*\s+для\s+ибп\b",
    r"\bбатарейн[а-яё]*\s+блок[а-яё]*\b|\bбатарейн[а-яё]*\s+массив[а-яё]*\b",
    r"\bсвинцово-кислот[а-яё]*\s+аккумулятор[а-яё]*\b",
    r"\bлитий-ион[а-яё]*\s+батаре[а-яё]*\s+ибп\b",
    r"\bсилов[а-яё]*\s+модул[а-яё]*\s+ибп\b",
    r"\bsnmp\s+плат[а-яё]*\b|\bплат[а-яё]*\s+сетевого\s+управления\s+ибп\b",
]

# Компиляция фильтров

COMPONENT_PATTERNS_IT3PH = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS_IT3PH]
BRAND_PATTERNS_IT3PH = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS_IT3PH]
FILTERS_WORK_PATTERNS_IT3PH = [re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_IT3PH]

# Функция фильтрация

def request_filters_it3ph(text: str, lots: list, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка проходит любой из фильтров,
    возвращая при этом номер категории.
    """

    has_component = _matches(COMPONENT_PATTERNS_IT3PH, text)
    has_brand = _matches(BRAND_PATTERNS_IT3PH, text)

    has_work_patterns = _matches(FILTERS_WORK_PATTERNS_IT3PH, text)

    result = False

    if has_work_patterns:
        result = True
        reason = "work_match: есть маркер батарей/комплектующих ИБП"

    elif has_component or has_brand:
        result = True
        reason = "brand_match: совпадение по поставке"

    elif has_okpd2_match(lots, TARGET_CODES_IT3PH):
        result = True
        reason = "has_okpd2_match: есть совпадения по базе okpd2"

    else:
        result = False
        reason = "no_match: нет релевантных маркеров по IT3PH"

    if debug:
        return {
            "result": result,
            "reason": reason,
            "filter_name": "IT3PH",
            "component": has_component,
            "brand": has_brand,
            "work_patterns": has_work_patterns,
            "normalized_text": text,
        }

    return {"result": result, "filter_name": "IT3PH"}


# Функция поиска совпадений okpd2

def has_okpd2_match(lots, target_codes):
    target_codes = set(target_codes)
    for lot in lots:
        for item in lot.get("items", []):
            if item.get("okpd2_code") in target_codes:
                return True
    return False


def request_filters_itm(work_name: str, lots: list, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка проходит любой из фильтров,
    возвращая при этом номер категории.
    """
    text = _normalize(work_name)

    itclg_filter = request_filters_itclg(text, lots)
    if itclg_filter["result"]:
        return itclg_filter

    itraa_filter = request_filters_itraa(text, lots)
    if itraa_filter["result"]:
        return itraa_filter

    itdig_filter = request_filters_itdig(text, lots)
    if itdig_filter["result"]:
        return itdig_filter

    it3ph_filter = request_filters_it3ph(text, lots)
    if it3ph_filter["result"]:
        return it3ph_filter

    return {"result": False}


# Вспомогательные функции

def _normalize(text: str) -> str:
    text = str(text or "")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[ \t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _matches(patterns, text: str):
    return [p.pattern for p in patterns if p.search(text)]


if __name__ == "__main__":
    lots = [
        {
            "guid": "f893f010-11f7-4637-9638-a31c9ee33958",
            "ordinal_number": "1",
            "subject": "прецизионый кондиционер",
            "initial_sum": 25219.54,
            "currency": "RUB",
            "items": [
                {
                    "guid": "729fea2d-f56d-432a-9d9a-e9e666d6b5fc",
                    "okpd2_code": "33.12.19.00",
                    "okpd2_name": "Услуги по ремонту и техническому обслуживанию прочего оборудования общего назначения, не включенного в другие группировки",
                    "additional_info": "Поддержание эксплуатационной готовности оборудования ЛКСМ, эксплуатируемого в Тиличикском отделении ОВД филиала «Камчатаэронавигация» ФГУП «Госкорпорация по ОрВД», в части ремонта ИБП из состава Наземной станции мониторинга и регистрации данных глобальной навигационной системы (ЛКСМ) с предустановленным программным обеспечением зав.№ 10134002Л"
                }
            ]
        },
        {
            "guid": "f893f010-11f7-4637-9638-a31c9ee33958",
            "ordinal_number": "1",
            "subject": "Поддержание эксплуатационной готовности оборудования ЛКСМ, эксплуатируемого в Тиличикском отделении ОВД филиала «Камчатаэронавигация» ФГУП «Госкорпорация по ОрВД», в части ремонта ИБП из состава Наземной станции мониторинга и регистрации данных глобальной навигационной системы (ЛКСМ) с предустановленным программным обеспечением зав.№ 10134002Л",
            "initial_sum": 25219.54,
            "currency": "RUB",
            "items": [
                {
                    "guid": "729fea2d-f56d-432a-9d9a-e9e666d6b5fc",
                    "okpd2_code": "43.22.2.120",
                    "okpd2_name": "Услуги по ремонту и техническому обслуживанию прочего оборудования общего назначения, не включенного в другие группировки",
                    "additional_info": "Поддержание эксплуатационной готовности оборудования ЛКСМ, эксплуатируемого в Тиличикском отделении ОВД филиала «Камчатаэронавигация» ФГУП «Госкорпорация по ОрВД», в части ремонта ИБП из состава Наземной станции мониторинга и регистрации данных глобальной навигационной системы (ЛКСМ) с предустановленным программным обеспечением зав.№ 10134002Л"
                }
            ]
        }
        ]
    print(request_filters_itm("прецизионый кондиционер", lots=lots))
