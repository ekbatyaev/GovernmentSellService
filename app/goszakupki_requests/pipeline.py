# import os
# from typing import Dict
#
# import requests
# from dotenv import load_dotenv
# from datetime import datetime, timedelta
# from pprint import pprint
# from app.goszakupki_requests.get_data_request import get_docs_by_region, download_archive_from_result
# from app.goszakupki_requests.get_data_parsed_fz_223_ri223 import parse_zip_archive
#
# load_dotenv()
#
# APP_URL = os.getenv("APP_URL")
# SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")
#
# def put_purchase_to_database(data: Dict):
#     try:
#         data["token"] = SYSTEM_TOKEN
#
#         response = requests.post(f"{APP_URL}/put_purchase", json = data)
#         print(f"Status: {response.status_code}")
#         pprint(response.json())
#         return
#     except Exception as e:
#         raise Exception(f"Ошибка: {e}")
#     finally:
#         return
#
#
# def get_all_purchases():
#     try:
#         response = requests.post(f"{APP_URL}/get_all_purchases", json={
#             "token": SYSTEM_TOKEN
#         })
#         print(f"Status: {response.status_code}")
#         pprint(response.json())
#     except Exception as e:
#         raise Exception(f"Ошибка: {e}")
#     finally:
#         return
#
#
# if __name__ == "__main__":
#     start_date = datetime.strptime("2025-02-23", "%Y-%m-%d")
#
#     num_days = 10
#
#     for i in range(num_days):
#         current_date = start_date + timedelta(days=i)
#         date_str = current_date.strftime("%Y-%m-%d")
#
#         # Запросы на скачивание
#         region_result = get_docs_by_region(
#             org_region="77",
#             document_type="purchaseNotice",
#             exact_date=date_str,
#             subsystem_type="RI223",
#         )
#
#         name_of_archive = download_archive_from_result(region_result)
#
#         data = parse_zip_archive(name_of_archive)
#
#         for purchase in data:
#             # /put_purchase - Положить закупку в базу
#             put_purchase_to_database(purchase)
#
#         # Получаем список всех закупок в базе
#
#         get_all_purchases()
#
#
#
#
#

import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

from app.goszakupki_requests.data_request import (
    get_docs_by_region,
    download_archive_from_result
)
from app.goszakupki_requests.parse_data_fz_223 import parse_zip_archive


load_dotenv()

APP_URL = os.getenv("APP_URL")
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")

TIMEOUT = 30

# ------------------------------------------------
# Logging
# ------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ------------------------------------------------
# HTTP Session (reuse connection)
# ------------------------------------------------

session = requests.Session()


# ------------------------------------------------
# API CLIENT
# ------------------------------------------------

def put_purchase_to_database(data: Dict) -> None:
    """
    Отправка закупки в FastAPI
    """

    payload = {**data, "token": SYSTEM_TOKEN}

    try:
        print(payload)
        response = session.post(
            f"{APP_URL}/put_purchase",
            json=payload,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        logger.info(
            "Purchase saved | guid=%s | status=%s",
            data.get("guid"),
            response.status_code
        )

    except requests.exceptions.RequestException as e:
        logger.error("Ошибка отправки закупки: %s", e)


def get_all_purchases() -> List[Dict]:
    """
    Получение списка всех закупок
    """

    try:
        response = session.post(
            f"{APP_URL}/get_all_purchases",
            json={"token": SYSTEM_TOKEN},
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        logger.info("Получено закупок из БД: %s", len(data))

        return data

    except requests.exceptions.RequestException as e:
        logger.error("Ошибка получения закупок: %s", e)
        return []


# ------------------------------------------------
# PROCESS ONE DAY
# ------------------------------------------------

def process_day(date_str: str) -> int:
    """
    Обработка одного дня закупок
    """

    logger.info("Обработка даты: %s", date_str)

    try:
        result = get_docs_by_region(
            org_region="77",
            document_type="purchaseNotice",
            exact_date=date_str,
            subsystem_type="RI223",
        )

        archive_name = download_archive_from_result(result)

        purchases = parse_zip_archive(archive_name)

        if not purchases:
            logger.info("Нет закупок после фильтрации")
            return 0

        saved = 0

        for purchase in purchases:
            put_purchase_to_database(purchase)
            saved += 1

        logger.info("Добавлено закупок: %s", saved)

        return saved

    except Exception as e:
        logger.error("Ошибка обработки даты %s: %s", date_str, e)
        return 0


# ------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------

def run_pipeline(start_date: str, days: int = 10):

    start = datetime.strptime(start_date, "%Y-%m-%d")

    total = 0

    for i in range(days):

        current_date = start + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        count = process_day(date_str)

        total += count

    logger.info("Pipeline завершён | всего добавлено закупок: %s", total)

    return total


# ------------------------------------------------
# MAIN
# ------------------------------------------------

if __name__ == "__main__":

    run_pipeline(
        start_date="2026-02-16",
        days=10
    )

    get_all_purchases()