import json
import re
import os
import zipfile
import logging

import xmltodict
import requests
from typing import Dict, List, Any
from .document_consistent import process_attached_files_and_merge

TMP_DIR = os.getenv("TMP_DIR", "tmp")
APP_URL = os.getenv("APP_URL")
API_BASE = os.getenv("API_BASE")
TOKEN = os.getenv("SYSTEM_TOKEN")

os.makedirs(TMP_DIR, exist_ok=True)

logger = logging.getLogger(__name__)

# Регионы для фильтров

REGIONS_ROSSETI = {"77": True}

# Фильтры для отбора документов

FILTERS_CUSTOMER = [r"\b(?:ПАО\s+)?Россети\s+Московск(?:ий|ого|ому|им|ом)?\s+регион(?:а|у|ом|е)?\b"]

FILTERS_JOB_NAME = [
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

FILTERS_JOB_EXCLUDE_HARD = [
    r"\bавто(?:мобил[а-я]*|транспорт[а-я]*|техник[а-я]*|шин[а-я]*|запчаст[а-я]*)\b",
    r"бензоинструмента",
    r"переустройств[а-я]*",
    r"кабельн[а-я]*\s+исполнени[а-я]*",
    r"воздушн[а-я]*\s+участк[а-я]*"
]

FILTERS_LINE_ONLY_ACTION = [
    r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
    r"(?:\d+\s*)?(?:КЛ|РКЛ|ВЛ|ВЛЗ|КВЛ|ЛЭП)\s*-?\s*\d+(?:\s*[,/]\s*\d+)?\s*кВ\b"
]


FILTERS_TARGET_OBJECT_ACTION = [
    r"\b(?:строительств[а-я]*|реконструкци[а-я]*|модернизаци[а-я]*)\s+"
    r"(?:нов[а-я]*\s+|встроенн[а-я]*\s+|выносн[а-я]*\s+)?"
    r"(?:\d+\s*)?"
    r"(?:РТП|БКТП|КТП|РП|ТП|РЩ)"
    r"\s*-?\s*"
    r"(?:№\s*\d+[А-ЯA-Zа-яa-z]?\s*)?"
    r"(?:\d+\s*/\s*0\s*,?\s*4|\d+)?"
    r"\s*(?:кВ)?\b"
]

FILTERS_JOB_EXCLUDE_SOFT = [
    r"\bПС(?:-\s*|\s+)(?:110|220|500)(?:/\d+)*\s*кВ\b"
]

TARGET_OBJECT_PATTERNS = [
    r"\bТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bРП\s*-?\s*(?:6|10|20)\s*(?:кВ)?\b",
    r"\bБКТП\s*-?\s*(?:6|10|20)?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
    r"\bКТП\s*-?\s*\d*(?:[-/]\s*(?:6|10|20))?(?:\s*/\s*0\s*,?\s*4)?\s*(?:кВ)?\b",
]

FILTERS_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_CUSTOMER]

JOB_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_NAME]

JOB_EXCLUDE_HARD_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_HARD
]

LINE_ONLY_ACTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_LINE_ONLY_ACTION
]

TARGET_OBJECT_ACTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_TARGET_OBJECT_ACTION
]

JOB_EXCLUDE_SOFT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in FILTERS_JOB_EXCLUDE_SOFT
]
TARGET_PATTERNS = [re.compile(p, re.IGNORECASE) for p in TARGET_OBJECT_PATTERNS]

FILTERS_OBJECTS = [

    # Щиты и шкафы управления

    r"\bшкаф\s+управлени[яа]\b",

    r"\bщит\s+управлени[яа]\b",

    r"\bШУ\b",

    r"\bЩУ\b",

    # Шкафы и щиты автоматики

    r"\bшкаф\s+автоматик[иа]\b",

    r"\bщит\s+автоматик[иа]\b",

    r"\bША\b",

    r"\bЩА\b",

    # НКУ

    r"\bНКУ\b",

    r"\bнизковольтн[а-я]*\s+комплектн[а-я]*\s+устройств[а-я]*\b",

    r"\bшкаф\s+НКУ\b",

    r"\bщит\s+НКУ\b",

    # АВР

    r"\bщит\s+АВР\b",

    r"\bшкаф\s+АВР\b",

    r"\bавтоматическ[а-я]*\s+ввод[а-я]*\s+резерв[а-я]*\b",

    # КИПиА

    r"\bщит\s+КИПи?А\b",

    r"\bшкаф\s+КИПи?А\b",

    r"\bКИПи?А\b",

    # Пульты и посты

    r"\bпульт\s+управлени[яа]\b",

    r"\bпульт\s+оператор[а-я]*\b",

    r"\bпост\s+управлени[яа]\b",

    r"\bвыносн[а-я]*\s+пульт\b",

    # Системы и аббревиатуры

    r"\bАСУ\s*ТП\b",

    r"\bАСУТП\b",

    r"\bАСУ\s*Э\b",

    r"\bСУЗ\b",

    r"\bсистем[а-я]*\s+управлени[яа]\s+задвижк[а-я]*\b",

    r"\bСАУ\b",

    r"\bсистем[а-я]*\s+автоматическ[а-я]*\s+управлени[яа]\b",

    r"\bСАК\b",

    r"\bсистем[а-я]*\s+автоматическ[а-я]*\s+контрол[яа]\b",

    r"\bАСДУ\b",

    r"\bавтоматизированн[а-я]*\s+систем[а-я]*\s+диспетчерск[а-я]*\s+управлени[яа]\b",

    r"\bSCADA\b",

    r"\bSCADA\s*[-–—]?\s*систем[а-я]*\b",

    r"\bСКАД[Аа]?\b",

    # Области применения

    r"\bавтоматизаци[а-я]*\s+котельн[а-я]*\b",

    r"\bавтоматизаци[а-я]*\s+(?:ИТП|ЦТП)\b",

    r"\bавтоматизаци[а-я]*\s+насосн[а-я]*\s+станци[а-я]*\b",

    r"\bавтоматизаци[а-я]*\s+вентиляци[а-я]*\b",

    r"\bавтоматизаци[а-я]*\s+очистн[а-я]*\s+сооружени[а-я]*\b",

    r"\bавтоматизаци[а-я]*\s+водоподготовк[иа]\b",

    r"\bэлектроснабжени[а-я]*\s+ЦОД\b",

]

# ------------------------------------------------------------

# Группа 2. Объекты управления: машины, установки, механизмы

# ------------------------------------------------------------

FILTERS_CONTROL_OBJECTS = [

    # Водоснабжение и водоотведение

    r"\bнасос[а-я]*\b",

    r"\bциркуляционн[а-я]*\s+насос[а-я]*\b",

    r"\bподпиточн[а-я]*\s+насос[а-я]*\b",

    r"\bпожарн[а-я]*\s+насос[а-я]*\b",

    r"\bдренажн[а-я]*\s+насос[а-я]*\b",

    r"\bскважинн[а-я]*\s+насос[а-я]*\b",

    r"\bсетев[а-я]*\s+насос[а-я]*\b",

    r"\bнасосн[а-я]*\s+станци[а-я]*\b",

    r"\bнасосн[а-я]*\s+групп[а-я]*\b",

    r"\bканализационн[а-я]*\s+насосн[а-я]*\s+станци[а-я]*\b",

    r"\bКНС\b",

    r"\bстанци[а-я]*\s+водоподготовк[иа]\b",

    r"\bочистн[а-я]*\s+сооружени[а-я]*\b",

    r"\bаэротенк[а-я]*\b",

    # ОВиК

    r"\bприточно\s*[-–—]?\s*вытяжн[а-я]*\s+установк[а-я]*\b",

    r"\bПВУ\b",

    r"\bприточн[а-я]*\s+установк[а-я]*\b",

    r"\bвытяжн[а-я]*\s+установк[а-я]*\b",

    r"\bкрышн[а-я]*\s+вентилятор[а-я]*\b",

    r"\bцентральн[а-я]*\s+систем[а-я]*\s+кондиционировани[а-я]*\b",

    r"\bчиллер[а-я]*\b",

    r"\bфанкойл[а-я]*\b",

    r"\bпрецизионн[а-я]*\s+кондиционер[а-я]*\b",

    r"\bградирн[а-я]*\b",

    r"\bузел\s+обвязк[иа]\b",

    # Промышленные механизмы

    r"\bконвейер[а-я]*\b",

    r"\bтранспортер[а-я]*\b",

    r"\bтранспорт[её]р[а-я]*\b",

    r"\bленточн[а-я]*\s+конвейер[а-я]*\b",

    r"\bдробилк[а-я]*\b",

    r"\bмельниц[а-я]*\b",

    r"\bсмесител[а-я]*\b",

    r"\bпитател[а-я]*\b",

    r"\bдозатор[а-я]*\b",

    r"\bсилос[а-я]*\b",

    r"\bкомпрессор[а-я]*\b",

    r"\bкомпрессорн[а-я]*\s+станци[а-я]*\b",

    r"\bцентрифуг[а-я]*\b",

    r"\bсепаратор[а-я]*\b",

    # Теплогенерация

    r"\bкот[её]л[а-я]*\b",

    r"\bгазов[а-я]*\s+кот[её]л[а-я]*\b",

    r"\bэлектрическ[а-я]*\s+кот[её]л[а-я]*\b",

    r"\bтвердотопливн[а-я]*\s+кот[её]л[а-я]*\b",

    r"\bблочно\s*[-–—]?\s*модульн[а-я]*\s+котельн[а-я]*\b",

    r"\bБМК\b",

    r"\bгорелк[а-я]*\b",

    r"\bгазораспределительн[а-я]*\s+пункт[а-я]*\b",

    r"\bГРПШ\b",

    r"\bтеплообменн[а-я]*\s+узел\b",

]

# ------------------------------------------------------------

# Группа 3. Продукция: начинка шкафов, компоненты

# ------------------------------------------------------------

FILTERS_COMPONENTS = [

    # Силовое оборудование

    r"\bпреобразователь\s+частот[ыа]\b",

    r"\bПЧ\b",

    r"\bЧРП\b",

    r"\bчастотно\s*[-–—]?\s*регулируем[а-я]*\s+привод\b",

    r"\bинвертор[а-я]*\b",

    r"\bустройств[а-я]*\s+плавн[а-я]*\s+пуск[а-я]*\b",

    r"\bУПП\b",

    r"\bсофт\s*[-–—]?\s*стартер[а-я]*\b",

    r"\bавтоматическ[а-я]*\s+выключател[а-я]*\b",

    r"\bвыключател[а-я]*\s+автоматическ[а-я]*\b",

    r"\bавтомат[а-я]*\b",

    r"\bВА\b",

    r"\bдифавтомат[а-я]*\b",

    r"\bУЗО\b",

    r"\bрубильник[а-я]*\b",

    r"\bразъединител[а-я]*\b",

    r"\bвыключател[а-я]*\s+нагрузк[иа]\b",

    r"\bконтактор[а-я]*\b",

    r"\bмагнитн[а-я]*\s+пускател[а-я]*\b",

    # Логика и визуализация

    r"\bПЛК\b",

    r"\bпрограммируем[а-я]*\s+логическ[а-я]*\s+контроллер[а-я]*\b",

    r"\bконтроллер\s+управлени[яа]\b",

    r"\bмодул[ьи]\s+ввода\s*[-–—]?\s*вывода\b",

    r"\bУСО\b",

    r"\bудаленн[а-я]*\s+ввод\s*[-–—]?\s*вывод\b",

    r"\bдискретн[а-я]*\s+ввод\s*[-–—]?\s*вывод\b",

    r"\bаналогов[а-я]*\s+ввод\s*[-–—]?\s*вывод\b",

    r"\bHMI\b",

    r"\bпанел[ьи]\s+оператор[а-я]*\b",

    r"\bсенсорн[а-я]*\s+панел[ьа-я]*\b",

    r"\bграфическ[а-я]*\s+панел[ьа-я]*\b",

    r"\bтерминал\s+оператор[а-я]*\b",

    # Реле и защита

    r"\bреле\s+промежуточн[а-я]*\b",

    r"\bреле\s+времени\b",

    r"\bреле\s+контрол[яа]\s+фаз\b",

    r"\bреле\s+напряжени[яа]\b",

    r"\bреле\s+ток[а-я]*\b",

    r"\bтеплов[а-я]*\s+реле\b",

    r"\bреле\s+перегрузк[иа]\b",

    r"\bтвердотельн[а-я]*\s+реле\b",

    r"\bТТР\b",

    # Коммутация и индикация

    r"\bсветосигнальн[а-я]*\s+арматур[а-я]*\b",

    r"\bкнопк[а-я]*\s+(?:пуск|стоп)\b",

    r"\bпереключател[а-я]*\b",

    r"\bселекторн[а-я]*\s+переключател[а-я]*\b",

    r"\bкулачков[а-я]*\s+переключател[а-я]*\b",

    r"\bпост\s+кнопочн[а-я]*\b",

    r"\bджойстик[а-я]*\b",

    r"\bиндикатор[а-я]*\b",

    r"\bсирен[а-я]*\b",

    r"\bзуммер[а-я]*\b",

    # Корпуса и монтаж

    r"\bшкаф\s+навесн[а-я]*\b",

    r"\bшкаф\s+напольн[а-я]*\b",

    r"\bоболочк[а-я]*\b",

    r"\bметаллокорпус[а-я]*\b",

]

# ------------------------------------------------------------

# Группа 4. Конкуренты и аналоги: бренды

# ------------------------------------------------------------

FILTERS_BRANDS = [

    # Щитовые компоненты / НВА

    r"\bESQ\b",

    r"\bNader\b",

    r"\bAKEL\b",

    r"\bIEK\b",

    r"\bИЕК\b",

    r"\bEKF\b",

    r"\bЕКФ\b",

    r"\bDKC\b",

    r"\bДКС\b",

    r"\bКЭАЗ\b",

    r"\bKEAZ\b",

    r"\bTengen\b",

    r"\bTDM\s*Electric\b",

    r"\bChint\b",

    r"\bЧинт\b",

    r"\bABB\b",

    r"\bАББ\b",

    r"\bSchneider\s*Electric\b",

    r"\bШнайдер\s*Электрик\b",

    r"\bSiemens\b",

    r"\bСименс\b",

    r"\bLS\s*Electric\b",

    r"\bHyundai\b",

    # Автоматизация / ПЛК / ПЧ / HMI

    r"\bInstart\b",

    r"\bОВЕН\b",

    r"\bOwen\b",

    r"\bOven\b",

    r"\bVeda\b",

    r"\bВеда\b",

    r"\bINVT\b",

    r"\bMaster\s*SCADA\b",

    r"\bDelta\s*Electronics\b",

    r"\bДельта\b",

    r"\bWeintek\b",

    r"\bВейнтек\b",

    r"\bWeinview\b",

    r"\bFatek\b",

    r"\bUnitronics\b",

    r"\bWago\b",

    r"\bВаго\b",

    r"\bBeckhoff\b",

    r"\bPhoenix\s*Contact\b",

    r"\bФеникс\s*Контакт\b",

    r"\bMitsubishi\b",

    r"\bOmron\b",

    r"\bYaskawa\b",

    r"\bLenze\b",

    r"\bDanfoss\b",

    r"\bДанфосс\b",

    r"\bGrundfos\b",

    r"\bInnovance\b",

    r"\bVeichi\b",

    r"\bVichi\b",

    r"\bSAJ\b",

    r"\bSinvel\b",

    r"\bElhart\b",

    r"\bIDS\b",

    r"\bInnovert\b",

    r"\bOptimus\s*Drive\b",

    r"\bОптимус\s*Драйв\b",

    r"\bPromPower\b",

    r"\bРусэлком\b",

    r"\bADL\b",

    # Российские производители ПЧ / УПП

    r"\bВеспер\b",

    r"\bVesper\b",

    r"\bЭлектротекс\b",

    r"\bНПО\s+Стоик\b",

    r"\bСтоик\b",

    r"\bТриол\b",

    r"\bСибирь\s*[-–—]?\s*М\b",

    r"\bЭлком\b",

    # Корпуса

    r"\bRittal\b",

    r"\bРитал\b",

    r"\bESB\b",

    r"\bПровенто\b",

]

# ------------------------------------------------------------

# Контекстные признаки

# ------------------------------------------------------------

FILTERS_WORK_CONTEXT = [

    r"\bпоставк[а-я]*\b",

    r"\bзакупк[а-я]*\b",

    r"\bизготовлени[а-я]*\b",

    r"\bпроизводств[а-я]*\b",

    r"\bсборк[а-я]*\b",

    r"\bмонтаж[а-я]*\b",

    r"\bшефмонтаж[а-я]*\b",

    r"\bпусконаладочн[а-я]*\b",

    r"\bПНР\b",

    r"\bпроектировани[а-я]*\b",

    r"\bразработк[а-я]*\b",

    r"\bмодернизаци[а-я]*\b",

    r"\bреконструкци[а-я]*\b",

    r"\bремонт[а-я]*\b",

    r"\bтехническ[а-я]*\s+обслуживани[а-я]*\b",

    r"\bТО\b",

    r"\bавтоматизаци[а-я]*\b",

    r"\bдиспетчеризаци[а-я]*\b",

    r"\bуправлени[а-я]*\b",

    r"\bэлектроснабжени[а-я]*\b",

    r"\bэлектрооборудовани[а-я]*\b",

]

# ------------------------------------------------------------

# Жесткие исключения

# ------------------------------------------------------------

FILTERS_EXCLUDE_HARD = [

    # Мебельные / бытовые / офисные шкафы

    r"\bшкаф\s+(?:одежн[а-я]*|платян[а-я]*|мебельн[а-я]*|офисн[а-я]*|архивн[а-я]*|книжн[а-я]*|медицинск[а-я]*|лабораторн[а-я]*|сушильн[а-я]*|жарочн[а-я]*|холодильн[а-я]*)\b",

    r"\bшкаф\s+для\s+(?:одежд[ыа]|документ[а-я]*|инвентар[яа]|посуд[ыа])\b",

    r"\bмебел[ьа-я]*\b",

    r"\bофисн[а-я]*\s+мебел[ьа-я]*\b",

    # Пожарные шкафы не как НКУ

    r"\bпожарн[а-я]*\s+шкаф\b",

    r"\bшкаф\s+пожарн[а-я]*\b",

    # IT / телеком без автоматизации

    r"\bсерверн[а-я]*\s+шкаф\b",

    r"\bшкаф\s+серверн[а-я]*\b",

    r"\bтелекоммуникационн[а-я]*\s+шкаф\b",

    r"\bкроссов[а-я]*\s+шкаф\b",

]

OBJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_OBJECTS]

CONTROL_OBJECT_PATTERNS = [

    re.compile(p, re.IGNORECASE) for p in FILTERS_CONTROL_OBJECTS

]

COMPONENT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_COMPONENTS]

BRAND_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FILTERS_BRANDS]

WORK_CONTEXT_PATTERNS = [

    re.compile(p, re.IGNORECASE) for p in FILTERS_WORK_CONTEXT

]

EXCLUDE_HARD_PATTERNS = [

    re.compile(p, re.IGNORECASE) for p in FILTERS_EXCLUDE_HARD

]

FIELDS = [
    "Победитель",
    "Другие участники",
    "Ячейки",
    "Кол-во ячеек",
    "Типовой проект",
    "Проектировщик",
    "Дата исполнения договора",
    "Филиал/РЭС",
]

def remove_ns(obj):
    if isinstance(obj, dict):
        new_dict = {}
        for k, v in obj.items():
            clean_key = k.split(":")[-1]
            new_dict[clean_key] = remove_ns(v)
        return new_dict
    if isinstance(obj, list):
        return [remove_ns(item) for item in obj]
    return obj


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]

def request_filters_rosseti(customer_name, work_name)-> bool:

    ok_customer = any(p.search(customer_name) for p in FILTERS_PATTERNS)
    excluded_hard = any(p.search(work_name) for p in JOB_EXCLUDE_HARD_PATTERNS)
    excluded_soft = any(p.search(work_name) for p in JOB_EXCLUDE_SOFT_PATTERNS)

    ok_job_raw = any(p.search(work_name) for p in JOB_PATTERNS)

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
        p.search(title_part) for p in LINE_ONLY_ACTION_PATTERNS
    )

    has_target_object_action = any(
        p.search(title_part) for p in TARGET_OBJECT_ACTION_PATTERNS
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
            r"(Россети\s+Московск[а-я]*\s+регион|для\s+нужд\s+(?:МКС|Новая\s+Москва))",
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



def request_filters_oem(work_name: str) -> bool:

    has_object = any(p.search(work_name) for p in OBJECT_PATTERNS)

    has_control_object = any(p.search(work_name) for p in CONTROL_OBJECT_PATTERNS)

    has_component = any(p.search(work_name) for p in COMPONENT_PATTERNS)

    has_brand = any(p.search(work_name) for p in BRAND_PATTERNS)

    has_context = any(p.search(work_name) for p in WORK_CONTEXT_PATTERNS)

    excluded = any(p.search(work_name) for p in EXCLUDE_HARD_PATTERNS)

    if excluded:

        return False

    # Прямые признаки: шкафы, щиты, АСУТП, ПЛК, ПЧ, бренды.

    if has_object or has_component or has_brand:

        return True

    # Косвенные признаки: насосы, котельные, вентиляция, конвейеры и т.п.

    # Засчитываем только при наличии контекста работ / поставки / управления.

    if has_control_object and has_context:

        return True

    return False

def normalize_protocol(data: dict) -> dict:

    body = data.get("purchaseProtocol", {}).get("body", {})
    item = body.get("item", {}) or {}
    protocol = item.get("purchaseProtocolData", {}) or {}
    purchase_info = protocol.get("purchaseInfo", {}) or {}
    lots_protocol_info = protocol.get("lotApplicationsList", {}).get("protocolLotApplications", {}) or {}

    result = {}

    result["guid"] = purchase_info.get("guid")
    result["registration_number"] = purchase_info.get("purchaseNoticeNumber")
    result["name"] = purchase_info.get("name")
    result["publication_datetime"] = protocol.get("publicationDateTime")
    result["submission_start_datetime"] = protocol.get("procedureDate", "")
    result["submission_close_datetime"] = protocol.get("procedureDate", "")

    customer = (protocol.get("customer") or {}).get("mainInfo") or {}
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    contact = protocol.get("contact") or {}
    result["contact"] = {
        "last_name": contact.get("lastName", ""),
        "first_name": contact.get("firstName", ""),
        "middle_name": contact.get("middleName", ""),
        "phone": contact.get("phone", ""),
        "email": contact.get("email", ""),
    }

    result["apply_request"] = {
        "submission_order": protocol.get("applSubmisionOrder", ""),
        "submission_place": protocol.get("applSubmisionPlace", "")
    }

    # начало работы с документами
    attached_files = protocol.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs
    # окончание работы с документами

    result["lots"] = []

    protocol_lot_applications = ensure_list(lots_protocol_info)

    for protocol_lot_application in protocol_lot_applications:
        protocol_lot_application = (
            protocol_lot_application
            if isinstance(protocol_lot_application, dict)
            else {}
        )

        lots = ensure_list(protocol_lot_application.get("lot"))

        for lot in lots:
            lot = lot if isinstance(lot, dict) else {}

            initial_sum_raw = lot.get("initialSum", 0) or 0
            try:
                initial_sum_val = float(initial_sum_raw)
            except Exception:
                initial_sum_val = 0.0

            lot_result = {
                "guid": lot.get("guid", ""),
                "ordinal_number": lot.get("ordinalNumber", ""),
                "subject": lot.get("subject", ""),
                "initial_sum": initial_sum_val,
                "currency": (lot.get("currency") or {}).get("code", "")
            }

            result["lots"].append(lot_result)


    result["initial_sum"] = sum(float(l.get("initial_sum") or 0) for l in result.get("lots", []))

    # начало работы с документами
    attached_files = protocol.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs

    result["publication_datetime"] = protocol.get("publicationDateTime")
    # окончание работы с документами

    return result

def parse_zip_archive_protocols(zip_path: str, region: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    with (zipfile.ZipFile(zip_path, "r") as archive):
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        logger.info("Найдено XML файлов: %s", len(xml_files))

        for file_name in xml_files:
            try:
                with archive.open(file_name) as file:
                    xml_content = file.read()

                data = xmltodict.parse(xml_content)
                data = remove_ns(data)
                normalized = normalize_protocol(data)
                normalized["source_file"] = file_name

                customer_name = (normalized.get("customer") or {}).get("full_name")
                work_name = normalized.get("name", "") or ""

                if REGIONS_ROSSETI.get(region, False) and request_filters_rosseti(customer_name, work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры Россетей"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data") or {}

                    if not purchase:

                        logger.info(
                            "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s",
                            normalized.get("registration_number"),
                        )

                        continue

                    result_info = purchase.get("result_info") or {}

                    documents_list = purchase.get("documents_list") or []

                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old=result_info,
                        documents_list_old=documents_list,
                        protocol_mode=True,
                        filter_type = 1
                    )

                    del normalized["attached_files"]

                    print("result_info - protocols")
                    print(normalized["result_info"])

                    print("documents_list - protocols")
                    print(normalized["documents_list"])
                    all_data.append(normalized)

                # if request_filters_oem(work_name):
                #     normalized["region_number"] = region
                #     normalized["filter_type_name"] = "Тендеры для OEM"
                #
                #     # Обращение, получение данных и передача
                #     purchase_response = requests.post(
                #         f"{APP_URL}{API_BASE}/get_purchase",
                #         json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                #         timeout=30,
                #     )
                #
                #     purchase_response.raise_for_status()
                #
                #     purchase = purchase_response.json().get("data") or {}
                #
                #     if not purchase:
                #         logger.info(
                #             "Протокол прошёл фильтр, но закупка не найдена в БД | reg=%s",
                #             normalized.get("registration_number"),
                #         )
                #
                #         continue
                #
                #     normalized["result_info"] = purchase.get("result_info") or {}
                #
                #     normalized["documents_list"] = purchase.get("documents_list") or []
                #
                #     # normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                #     #     attached_files=normalized["attached_files"],
                #     #     tmp_dir=TMP_DIR,
                #     #     result_info_old=result_info,
                #     #     documents_list_old=documents_list,
                #     #     protocol_mode=True,
                #     #     filter_type = 2
                #     # )
                #     #
                #     # del normalized["attached_files"]
                #     #
                #     # print("result_info - protocols")
                #     # print(normalized["result_info"])
                #     #
                #     # print("documents_list - protocols")
                #     # print(normalized["documents_list"])
                #     all_data.append(normalized)


            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)

    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data


def normalize_purchase(data: dict) -> dict:

    body = data.get("purchaseNotice", {}).get("body", {})
    item = body.get("item", {}) or {}
    notice = item.get("purchaseNoticeData", {}) or {}

    result = {}

    result["guid"] = item.get("guid")
    result["registration_number"] = notice.get("registrationNumber")
    result["name"] = notice.get("name")
    result["publication_datetime"] = notice.get("publicationDateTime")
    submission_start = notice.get("applSubmisionStartDate")
    result["submission_start_datetime"] = (
        f"{submission_start}T00:00:00" if submission_start else None
    )
    result["submission_close_datetime"] = notice.get("submissionCloseDateTime")

    customer = (notice.get("customer") or {}).get("mainInfo") or {}
    result["customer"] = {
        "full_name": customer.get("fullName"),
        "inn": customer.get("inn"),
        "kpp": customer.get("kpp"),
        "ogrn": customer.get("ogrn"),
    }

    contact = notice.get("contact") or {}
    result["contact"] = {
        "last_name": contact.get("lastName"),
        "first_name": contact.get("firstName"),
        "middle_name": contact.get("middleName"),
        "phone": contact.get("phone"),
        "email": contact.get("email"),
    }

    result["apply_request"] = {
        "submission_order": notice.get("applSubmisionOrder"),
        "submission_place": notice.get("applSubmisionPlace")
    }


    # начало работы с документами
    attached_files = notice.get("attachments") or {}
    document = attached_files.get("document")
    if isinstance(document, str):
        try:
            document = json.loads(document)
        except Exception:
            document = None
    document = ensure_list(document)
    docs = []

    for doc in document:
        docs.append({
            "filename": doc["fileName"],
            "description": doc["description"],
            "url": doc["url"]
        })

    result["attached_files"] = docs
    # окончание работы с документами

    result["lots"] = []
    lots = ensure_list((notice.get("lots") or {}).get("lot"))

    for lot in lots:
        lot = lot or {}
        lot_data = (lot.get("lotData") or {}) if isinstance(lot, dict) else {}

        initial_sum_raw = lot_data.get("initialSum", 0) or 0
        try:
            initial_sum_val = float(initial_sum_raw)
        except Exception:
            initial_sum_val = 0.0

        lot_result = {
            "guid": lot.get("guid"),
            "ordinal_number": lot.get("ordinalNumber"),
            "subject": lot_data.get("subject"),
            "initial_sum": initial_sum_val,
            "currency": (lot_data.get("currency") or {}).get("code"),
            "application_supply_summ": lot_data.get("applicationSupplySumm"),
            "application_supply_extra": lot_data.get("applicationSupplyExtra"),
            "completing_supply_summ": (lot_data.get("completingSupplyInfo") or {}).get("sum"),
            "items": [],
        }

        lot_items = ensure_list((lot_data.get("lotItems") or {}).get("lotItem"))
        for it in lot_items:
            it = it or {}
            lot_result["items"].append(
                {
                    "guid": it.get("guid"),
                    "okpd2_code": (it.get("okpd2") or {}).get("code"),
                    "okpd2_name": (it.get("okpd2") or {}).get("name"),
                    "qty": it.get("qty"),
                    "additional_info": it.get("additionalInfo"),
                }
            )

        result["lots"].append(lot_result)

    result["initial_sum"] = sum(float(l.get("initial_sum") or 0) for l in result.get("lots", []))
    return result


def parse_zip_archive_purchases(zip_path: str, region: int) -> List[Dict[str, Any]]:
    zip_path = os.path.abspath(zip_path)
    all_data: List[Dict[str, Any]] = []
    logger.info("Открываем архив: %s", zip_path)

    with (zipfile.ZipFile(zip_path, "r") as archive):
        xml_files = [f for f in archive.namelist() if f.lower().endswith(".xml")]
        logger.info("Найдено XML файлов: %s", len(xml_files))

        for file_name in xml_files:
            try:
                with archive.open(file_name) as file:
                    xml_content = file.read()

                data = xmltodict.parse(xml_content)
                data = remove_ns(data)
                normalized = normalize_purchase(data)
                normalized["source_file"] = file_name

                customer_name = (normalized.get("customer") or {}).get("full_name")
                work_name = normalized.get("name", "") or ""

                if REGIONS_ROSSETI.get(region, False) and request_filters_rosseti(customer_name, work_name):
                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры Россетей"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    result_info = purchase.get("result_info") or {}

                    match = re.search(r'для нужд\s+([^.,()\-–—]+)', normalized["name"], re.IGNORECASE)

                    if match:

                        value = match.group(1).strip()

                        first_word = value.split()[0]

                        result_info["Филиал/РЭС"] = value if len(first_word) > 4 else first_word

                    else:

                        result_info["Филиал/РЭС"] = None

                    documents_list = purchase.get("documents_list") or []

                    normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                        attached_files=normalized["attached_files"],
                        tmp_dir=TMP_DIR,
                        result_info_old = result_info,
                        documents_list_old = documents_list,
                        filter_type = 1
                    )

                    del normalized["attached_files"]

                    all_data.append(normalized)

                if request_filters_oem(work_name):

                    normalized["region_number"] = region
                    normalized["filter_type_name"] = "Тендеры для OEM"

                    # Обращение, получение данных и передача
                    purchase_response = requests.post(
                        f"{APP_URL}{API_BASE}/get_purchase",
                        json={"token": TOKEN, "registration_number": normalized["registration_number"]},
                        timeout=30,
                    )

                    purchase_response.raise_for_status()

                    purchase = purchase_response.json().get("data", {})

                    normalized["result_info"] = purchase.get("result_info") or {}

                    normalized["documents_list"] = purchase.get("documents_list") or []

                    # result_info = purchase.get("result_info") or {}
                    #
                    # documents_list = purchase.get("documents_list") or []
                    #
                    # normalized["result_info"], normalized["documents_list"] = process_attached_files_and_merge(
                    #     attached_files=normalized["attached_files"],
                    #     tmp_dir=TMP_DIR,
                    #     result_info_old=result_info,
                    #     documents_list_old=documents_list,
                    #     filter_type = 2
                    # )

                    del normalized["attached_files"]

                    all_data.append(normalized)

            except Exception as e:
                logger.exception("Ошибка в файле %s: %s", file_name, e)
    logger.info("Парсинг завершён. Подходит под фильтры: %s", len(all_data))
    os.remove(zip_path)
    return all_data

if __name__ == "__main__":
    merged_fields = process_attached_files_and_merge(
        attached_files=[
            {
                "filename": "624 Протокол итоговый.docx",
                "description": "",
                "url": "URL_СЮДА"
            }
        ],
        tmp_dir=TMP_DIR,
    )