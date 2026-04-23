import json
import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta
from pprint import pprint

import requests
from dotenv import load_dotenv

from app.goszakupki_requests.data_request import get_docs_by_region, download_archive_from_result
from app.goszakupki_requests.parse_data_fz_223 import parse_zip_archive_purchases, parse_zip_archive_protocols

load_dotenv()

APP_URL = os.getenv("APP_URL", "http://localhost:8000")
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")

TIMEOUT = 60

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

session = requests.Session()


def put_purchase_to_database(data: Dict) -> None:
    if not SYSTEM_TOKEN:
        raise RuntimeError("SYSTEM_TOKEN is required")

    payload = {**data, "token": SYSTEM_TOKEN}

    try:
        response = session.post(f"{APP_URL}/put_purchase", json=payload, timeout=TIMEOUT)
        # put_purchase может вернуть 201 или 200 (если already exists) в нашей реализации
        if response.status_code not in (200, 201):
            logger.error("put_purchase failed | status=%s body=%s", response.status_code, response.text)
            return
        logger.info("Purchase saved | guid=%s | status=%s", data.get("guid"), response.status_code)
    except requests.exceptions.RequestException as e:
        logger.error("Ошибка отправки закупки: %s", e)


def get_all_purchases() -> List[Dict]:
    if not SYSTEM_TOKEN:
        raise RuntimeError("SYSTEM_TOKEN is required")

    try:
        response = session.post(f"{APP_URL}/get_all_purchases", json={"token": SYSTEM_TOKEN}, timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
        data = body.get("data", [])
        logger.info("Получено закупок из БД: %s", len(data))
        return data
    except requests.exceptions.RequestException as e:
        logger.error("Ошибка получения закупок: %s", e)
        return []


def process_day(date_str: str) -> int:
    logger.info("Обработка даты: %s", date_str)
    try:
        # result_purchases = get_docs_by_region(
        #     org_region="77",
        #     document_type="purchaseNotice",
        #     exact_date=date_str,
        #     subsystem_type="RI223",
        # )

        result_protocols = get_docs_by_region(
            org_region="77",
            document_type="purchaseProtocol",
            exact_date=date_str,
            subsystem_type="RI223",
        )
        #
        # zip_path_purchases = download_archive_from_result(result_purchases)

        zip_path_protocols = download_archive_from_result(result_protocols)

        # purchases = parse_zip_archive_purchases(zip_path_purchases)

        protocols = parse_zip_archive_protocols(zip_path_protocols)

        # saved = 0
        # for purchase in purchases:
        #     # put_purchase_to_database(purchase)
        #     saved += 1
        #
        # logger.info("Добавлено закупок: %s", saved)
        # return saved
        #
        # protocols_new = parse_zip_archive_protocols(zip_path)
        #

        file_path = "protocols.json"  # или "/app/protocols.json"

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                protocols_old = json.load(file)
        except FileNotFoundError:
            protocols_old = []  # если файла нет, начинаем с пустого списка

        # Убедимся, что это список
        if not isinstance(protocols_old, list):
            protocols_old = []

        # Добавляем новые протоколы (лучше extend, но можно и цикл)
        protocols_old.extend(protocols)  # protocols — это ваш новый список

        # Записываем обратно
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(protocols_old, file, indent=4, ensure_ascii=False)

        return len(protocols)
    except Exception as error:
        print(error)


def run_pipeline(start_date: str, days: int = 10) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    total = 0
    for i in range(days):
        current_date = start + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        total += process_day(date_str)
    logger.info("Pipeline завершён | всего обработано: %s", total)
    return total


if __name__ == "__main__":
    # # пример: последние 10 дней до вчера
    # today = datetime.now().date()
    # start = today - timedelta(days=10)
    # run_pipeline(start_date=start.strftime("%Y-%m-%d"), days=10)
    # get_all_purchases()
    from datetime import date, timedelta

    current = date(2026, 3, 10)
    end = date(2026, 3, 30)

    while current < end:
        process_day(current.isoformat())
        current += timedelta(days=1)