import re
from typing import Union, Dict, Any

# Фильтры в формате регулярных выражений

# 1. Прямые маркеры объекта закупки: ИБП / UPS

FILTERS_OBJECT_ITM = [
    r"\bибп\b",
    r"\bи\.?\s*б\.?\s*п\.?\b",

    r"\bисточник[а-яё]*\s+бесперебойн[а-яё]*\s+питани[а-яё]*\b",
    r"\bисточник[а-яё]*\s+бесперебойн[а-яё]*\s+электропитани[а-яё]*\b",
    r"\bисточник[а-яё]*\s+резервн[а-яё]*\s+питани[а-яё]*\b",

    r"\bups\b",
    r"\buninterruptible\s+power\s+supply\b",
    r"\bбесперебойн[а-яё]*\s+питани[а-яё]*\b",
    r"\bсистем[а-яё]*\s+бесперебойн[а-яё]*\s+питани[а-яё]*\b",
]


# 2. Компоненты ИБП.
# Сами по себе они слабее, чем ИБП, но помогают находить закупки,
# где ИБП описан через состав оборудования.

FILTERS_COMPONENTS_ITM = [
    r"\bаккумуляторн[а-яё]*\s+батаре[а-яё]*\b",
    r"\bакб\b",
    r"\bбатарейн[а-яё]*\s+модул[а-яё]*\b",
    r"\bбатарейн[а-яё]*\s+кабинет[а-яё]*\b",
    r"\bбатарейн[а-яё]*\s+шкаф[а-яё]*\b",

    r"\bбайпас[а-яё]*\b",
    r"\bbypass\b",
    r"\bстатическ[а-яё]*\s+байпас[а-яё]*\b",

    r"\bинвертор[а-яё]*\b",
    r"\bвыпрямител[а-яё]*\b",
    r"\bзарядн[а-яё]*\s+устройств[а-яё]*\b",
]


# 3. Бренды производителей ИБП.
# Бренд не должен автоматически включать всё подряд,
# но вместе с поставкой или ИБП является сильным сигналом.

FILTERS_BRANDS_ITM = [
    r"\bapc\b",
    r"\bschneider\s+electric\b",
    r"\beaton\b",
    r"\bliebert\b",
    r"\bvertiv\b",
    r"\bdelt[аa]\b",
    r"\bdkc\b",
    r"\bsvensson\b",
    r"\bippon\b",
    r"\bpowercom\b",
    r"\bcyberpower\b",
    r"\bsocomec\b",
    r"\briello\b",
    r"\bkehua\b",
    r"\bhuawei\b",
    r"\bсайберпауэр\b",
    r"\bиппон\b",
]


# 4. Маркеры поставки / нового оборудования.
# Это ключевая группа для отличия поставки от обслуживания.

FILTERS_WORK_ITM = [
    r"\bпоставк[а-яё]*\b",
    r"\bпоставить\b",
    r"\bпоставляем[а-яё]*\b",
    r"\bприобретени[а-яё]*\b",
    r"\bзакупк[а-яё]*\b",
    r"\bкомплектаци[а-яё]*\b",
    r"\bоснащени[а-яё]*\b",
    r"\bдооснащени[а-яё]*\b",

    r"\bпоставка\s+и\s+монтаж\b",
    r"\bпоставка\s+с\s+монтаж[а-яё]*\b",
    r"\bпоставка\s*,?\s+монтаж\b",

    r"\bпоставка\s+и\s+настройк[а-яё]*\b",
    r"\bпоставка\s+и\s+пуско[-\s]?наладочн[а-яё]*\s+работ[а-яё]*\b",
    r"\bпоставка\s+и\s+пнр\b",

    r"\bпоставка\s+и\s+испытани[а-яё]*\b",
    r"\bпоставка\s+и\s+ввод\s+в\s+эксплуатаци[а-яё]*\b",
    r"\bввод\s+в\s+эксплуатаци[а-яё]*\s+ибп\b",

    r"\bмонтаж[а-яё]*\s+ибп\b",
    r"\bустановк[а-яё]*\s+ибп\b",
    r"\bзамен[а-яё]*\s+ибп\b",
    r"\bзамен[а-яё]*\s+источник[а-яё]*\s+бесперебойн[а-яё]*\s+питани[а-яё]*\b",

    r"\bоборудовани[а-яё]*\b",
    r"\bкомплект[а-яё]*\s+ибп\b",
]


# 5. Принудительные включения.
# Сюда можно добавлять фразы из размеченной таблицы,
# которые система ошибочно отсекает, но они точно релевантны.

FILTERS_INCLUDE_FORCE_ITM = [
    r"\bпоставк[а-яё]*\s+ибп\b",
    r"\bпоставк[а-яё]*\s+источник[а-яё]*\s+бесперебойн[а-яё]*\s+питани[а-яё]*\b",
    r"\bпоставк[а-яё]*\s+ups\b",

    r"\bпоставка\s+и\s+техническ[а-яё]*\s+обслуживани[а-яё]*\s+ибп\b",
    r"\bпоставка\s+ибп\s+с\s+последующ[а-яё]*\s+обслуживани[а-яё]*\b",

    r"\bпоставка\s+и\s+монтаж\s+ибп\b",
    r"\bпоставка\s+и\s+настройк[а-яё]*\s+ибп\b",
    r"\bпоставка\s+и\s+испытани[а-яё]*\s+ибп\b",
]


# 6. Принудительные исключения.
# Для калибровки по размеченной таблице.

FILTERS_EXCLUDE_FORCE_ITM = [
    r"\bпродлени[а-яё]*\s+гаранти[а-яё]*\s+на\s+ибп\b",
    r"\bпродлени[а-яё]*\s+сервисн[а-яё]*\s+поддержк[а-яё]*\s+ибп\b",
]


# 7. Жесткие исключения: только сервис / ремонт / ТО.
# Важно: эти исключения НЕ должны срабатывать, если есть поставка.
# Поэтому в логике ниже они проверяются как "service_only".

FILTERS_EXCLUDE_HARD_ITM = [
    r"\bтехническ[а-яё]*\s+обслуживани[а-яё]*\b",
    r"\bтехобслуживани[а-яё]*\b",
    r"\bто\s+ибп\b",

    r"\bсервисн[а-яё]*\s+обслуживани[а-яё]*\b",
    r"\bсервис[а-яё]*\s+ибп\b",
    r"\bсервисн[а-яё]*\s+поддержк[а-яё]*\b",

    r"\bремонт[а-яё]*\b",
    r"\bдиагностик[а-яё]*\b",
    r"\bрегламентн[а-яё]*\s+работ[а-яё]*\b",
    r"\bпрофилактическ[а-яё]*\s+работ[а-яё]*\b",

    r"\bвосстановлени[а-яё]*\s+работоспособност[а-яё]*\b",
    r"\bустранени[а-яё]*\s+неисправност[а-яё]*\b",

    r"\bпродлени[а-яё]*\s+гаранти[а-яё]*\b",
    r"\bгарантийн[а-яё]*\s+обслуживани[а-яё]*\b",
    r"\bпостгарантийн[а-яё]*\s+обслуживани[а-яё]*\b",
]


# 8. Мягкие исключения.
# Они нужны для общих закупок без явного ИБП / поставки.

FILTERS_EXCLUDE_SOFT_ITM = [
    r"\bоказани[а-яё]*\s+услуг[а-яё]*\b",
    r"\bвыполнени[а-яё]*(?:\s+[а-яё-]+){0,8}\s+работ[а-яё]*\b",
    r"\bаукцион\b",
    r"\bзапрос\s+котировок\b",
    r"\bэлектронн[а-яё]*\s+аукцион\b",
]

# Компиляция фильтров

OBJECT_PATTERNS_ITM= [re.compile(p, re.IGNORECASE) for p in FILTERS_OBJECT_ITM]
COMPONENT_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS_ITM]
BRAND_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS_ITM]
FILTERS_WORK_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_ITM]
EXCLUDE_FORCE_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_EXCLUDE_FORCE_ITM]
INCLUDE_FORCE_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_INCLUDE_FORCE_ITM]
EXCLUDE_HARD_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_EXCLUDE_HARD_ITM]
EXCLUDE_SOFT_PATTERNS_ITM = [re.compile(p, re.IGNORECASE) for p in FILTERS_EXCLUDE_SOFT_ITM]

# Функция фильтрация

def request_filters_itm(work_name: str, debug: bool = False) -> Union[bool, Dict[str, Any]]:
    """
    Возвращает True, если закупка связана с поставкой ИБП / UPS.

    Логика:
    - "поставка ИБП" -> True
    - "поставка и обслуживание ИБП" -> True
    - "техническое обслуживание ИБП" -> False
    - "ремонт ИБП" -> False
    - "продление гарантии на ИБП" -> False
    """
    text = _normalize(work_name)

    force_exclude = _matches(EXCLUDE_FORCE_PATTERNS_ITM, text)
    force_include = _matches(INCLUDE_FORCE_PATTERNS_ITM, text)

    has_object = _matches(OBJECT_PATTERNS_ITM, text)
    has_component = _matches(COMPONENT_PATTERNS_ITM, text)
    has_brand = _matches(BRAND_PATTERNS_ITM, text)

    has_supply = _matches(FILTERS_WORK_PATTERNS_ITM, text)

    excluded_hard = _matches(EXCLUDE_HARD_PATTERNS_ITM, text)
    excluded_soft = _matches(EXCLUDE_SOFT_PATTERNS_ITM, text)

    has_ups_marker = bool(has_object or has_component or has_brand)

    # Главный семантический флаг:
    # обслуживание/ремонт есть, но поставки нового оборудования нет.
    service_only = bool(excluded_hard) and not bool(has_supply)

    reason = ""
    result = False

    # 0) Принудительные исключения.
    if force_exclude:
        result = False
        reason = "force_exclude: закупка явно относится только к сервису/гарантии без поставки"

    # 1) Принудительные включения.
    elif force_include:
        result = True
        reason = "force_include: закупка явно содержит поставку ИБП"

    # 2) Только обслуживание / ремонт / сервис ИБП.
    elif has_ups_marker and service_only:
        result = False
        reason = "service_only: есть ИБП, но предмет только обслуживание/ремонт/сервис без поставки"

    # 3) ИБП + поставка / монтаж / настройка / испытания / ввод.
    elif has_ups_marker and has_supply:
        result = True
        reason = "supply_match: есть маркер ИБП и признак поставки/монтажа/настройки/испытаний"

    # 4) Сильный прямой маркер ИБП без сервисных исключений.
    # Можно оставить True, если тебе нужно ловить короткие названия вроде "ИБП".
    # Если нужно строже — замени result на False.
    elif has_object and not excluded_hard:
        result = True
        reason = "object_match: есть прямой маркер ИБП без признаков только обслуживания"

    # 5) Компоненты/бренды без поставки — слабый сигнал.
    elif has_component or has_brand:
        result = False
        reason = "weak_match: есть компонент/бренд, но нет явной поставки ИБП"

    # 6) Общие мягкие исключения.
    elif excluded_soft:
        result = False
        reason = "soft_exclude: общий тендер без релевантных маркеров поставки ИБП"

    else:
        result = False
        reason = "no_match: нет релевантных маркеров ИБП"

    if debug:
        return {
            "result": result,
            "reason": reason,
            "force_exclude": force_exclude,
            "force_include": force_include,
            "object": has_object,
            "component": has_component,
            "brand": has_brand,
            "supply": has_supply,
            "exclude_hard": excluded_hard,
            "exclude_soft": excluded_soft,
            "service_only": service_only,
            "normalized_text": text,
        }

    return result

# Вспомогательные функции

def _normalize(text: str) -> str:
    text = str(text or "")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[\u00A0\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _matches(patterns, text: str):
    return [p.pattern for p in patterns if p.search(text)]