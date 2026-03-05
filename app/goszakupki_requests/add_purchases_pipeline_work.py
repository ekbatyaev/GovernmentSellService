import os
from typing import Dict

import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from pprint import pprint
from app.goszakupki_requests.get_data_request import get_docs_by_region, download_archive_from_result
from app.goszakupki_requests.get_data_parsed_fz_223_ri223 import parse_zip_archive

load_dotenv()

APP_URL = os.getenv("APP_URL")
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")

def put_purchase_to_database(data: Dict):
    try:
        data["token"] = SYSTEM_TOKEN

        response = requests.post(f"{APP_URL}/put_purchase", json = data)
        print(f"Status: {response.status_code}")
        pprint(response.json())
        return
    except Exception as e:
        raise("Ошибка: ", e)


def get_all_purchases():
    try:
        response = requests.post(f"{APP_URL}/get_all_purchases", json={
            "token": SYSTEM_TOKEN
        })
        print(f"Status: {response.status_code}")
        pprint(response.json())
        return
    except Exception as e:
        raise ("Ошибка: ", e)


if __name__ == "__main__":
    start_date = datetime.strptime("2025-02-23", "%Y-%m-%d")

    num_days = 10

    for i in range(num_days):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")

        # Запросы на скачивание
        region_result = get_docs_by_region(
            org_region="77",
            document_type="purchaseNotice",
            exact_date=date_str,
            subsystem_type="RI223",
        )

        name_of_archive = download_archive_from_result(region_result)

        data = parse_zip_archive(name_of_archive)

        for purchase in data:
            # /put_purchase - Положить закупку в базу
            put_purchase_to_database(purchase)

        # Получаем список всех закупок в базе

        pprint(get_all_purchases())





