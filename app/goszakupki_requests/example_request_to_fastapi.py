import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

# APP_URL = os.getenv("APP_URL")
APP_URL = "http://127.0.0.1:8002/goszakupki"
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")
print(f"APP_URL: {APP_URL}")

# 1. POST /put_purchase - Создать закупку
# print("\n" + "="*50)
# print("1. Creating purchase...")
response = requests.post(f"{APP_URL}/put_purchase", json={
    "token": SYSTEM_TOKEN,
    "guid": "124",
    "registration_number": "32615787390",
    "name": "Тестовая закупка - 2",
    "source_file": "file.pdf",
    "initial_sum": 1000.0,
    "publication_datetime": datetime.now().isoformat(),
    "submission_start_datetime": datetime.now().isoformat(),
    "submission_close_datetime": datetime.now().isoformat(),
    "customer": {"name": "Customer", "inn": "1234567890"},
    "contact": {"email": "test@test.com", "phone": "+71234567890"},
    "apply_request": {"status": "open", "requests": 5},
    "lots": [{"number": 1, "description": "Main lot"}]
})

print(response.json())

# response = requests.post(f"{APP_URL}/put_purchase", json={
#     "token": SYSTEM_TOKEN,
#     "guid": "f2721f61-c78a-4209-860f-682b9de2c930",  # реальный guid
#     "registration_number": "32515482193",  # реальный номер
#     "name": "Определение подрядчика на выполнение СМР, ПНР, оборудование по титулу: Модернизация ПС 110/6 кВ № 387 «Подрезково»",
#     "source_file": "purchaseNotice_32515482193_10_019C655D5AFA7C63A473C5319711261B.xml",
#     "initial_sum": 785278.25,  # сумма из первого лота
#     "publication_datetime": "2026-02-16T10:32:19",
#     "submission_close_datetime": "2026-03-02T11:00:00",
#
#     # Customer (заказчик)
#     "customer": {
#         "full_name": "ПУБЛИЧНОЕ АКЦИОНЕРНОЕ ОБЩЕСТВО \"РОССЕТИ МОСКОВСКИЙ РЕГИОН\"",
#         "inn": "5036065113",
#         "kpp": "772501001",
#         "ogrn": "1057746555811"
#     },
#
#     # Contact (контактное лицо)
#     "contact": {
#         "last_name": "Солоненкова",
#         "first_name": "М.",
#         "middle_name": "В.",
#         "phone": "+7 (495) 6624070, доб.: 4704",
#         "email": "SolonenkovaMV@ROSSETIMR.RU"
#     },
#
#     # Apply request (подача заявок)
#     "apply_request": {
#         "submission_order": "В соответствии с документацией",
#         "submission_place": None,
#         "submission_start_date": "2025-12-03"
#     },
#
#     "lots": [{
#         "guid": "316bd8f7-a528-4b5b-a940-cfea95b2a81f",
#         "ordinal_number": "1",
#         "subject": "Выполнение СМР, ПНР, оборудование по титулу: Модернизация ПС 110/6 кВ № 387 «Подрезково»",
#         "initial_sum": 785278.25,
#         "currency": "RUB",
#         "items": [
#             {
#                 "guid": "4d157250-b679-4b18-b9cd-eafe28434298",
#                 "okpd2_code": "42.22.22.120",
#                 "okpd2_name": "Работы строительные по строительству трансформаторных станций и подстанций",
#                 "qty": "1",
#                 "additional_info": None
#             }
#         ]
#     }]
# })
#
# print(f"Status: {response.status_code}")
# print(response.text)
# pprint(response.json())

# # 2. POST /get_purchase - Получить закупку
# print("\n" + "="*50)
# print("2. Getting purchase...")
# response = requests.post(f"{APP_URL}/get_purchase", json={
#     "token": SYSTEM_TOKEN,
#     "guid": "b4fbce07-0b7c-40ad-9911-a2861d2d284c"
# })
# print(response.json())
#
# print(f"Status: {response.status_code}")
# pprint(response.json())
#
# # 3. PUT /update_purchase - Обновить закупку
# print("\n" + "="*50)
# print("3. Updating purchase...")
# response = requests.put(f"{APP_URL}/update_purchase", json={
#     "token": SYSTEM_TOKEN,
#     "guid": "123",
#     "name": "Обновленная тестовая закупка",
#     "initial_sum": 2000.0
# })
#
# print(f"Status: {response.status_code}")
# pprint(response.json())
#
# 4. POST /get_all_purchases - Получить список с фильтрами
# print("\n" + "="*50)
# print("4. Getting all purchases with filters...")
# response = requests.post(f"{APP_URL}/get_all_purchases", json={
#     "token": SYSTEM_TOKEN,
#     "name": "тестовая",
#     "initial_sum_from": 500,
#     "initial_sum_to": 5000
# })

# 4. POST /get_all_purchases - Получить список с фильтрами
# print("\n" + "="*50)
# print("4. Getting all purchases with filters...")
# response = requests.post(f"{APP_URL}/get_all_purchases", json={
#     "token": SYSTEM_TOKEN
# })
# #
# print(f"Status: {response.status_code}")
# pprint(response.json())
#
# # 5. GET /stats - Статистика
# print("\n" + "="*50)
# print("5. Getting statistics...")
# response = requests.get(f"{APP_URL}/stats")
#
# print(f"Status: {response.status_code}")
# pprint(response.json())
#
# # 6. GET /health - Проверка здоровья
# print("\n" + "="*50)
# print("6. Health check...")
# response = requests.get(f"{APP_URL}/health")
#
# print(f"Status: {response.status_code}")
# pprint(response.json())
#
# # 7. DELETE /delete_purchase - Удалить закупку
# print("\n" + "="*50)
# print("7. Deleting purchase...")
# response = requests.delete(f"{APP_URL}/delete_purchase", json={
#     "token": SYSTEM_TOKEN,
#     "guid": "123"
# })
#
# print(f"Status: {response.status_code}")
# pprint(response.json())