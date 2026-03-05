import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

APP_URL = os.getenv("APP_URL")
SYSTEM_TOKEN = os.getenv("SYSTEM_TOKEN")
print(f"APP_URL: {APP_URL}")

# 1. POST /put_purchase - Создать закупку
print("\n" + "="*50)
print("1. Creating purchase...")
response = requests.post(f"{APP_URL}/put_purchase", json={
    "token": SYSTEM_TOKEN,
    "guid": "123",
    "registration_number": "REG001",
    "name": "Тестовая закупка",
    "source_file": "file.pdf",
    "initial_sum": 1000.0,
    "created_at": datetime.now().isoformat(),
    "publication_datetime": datetime.now().isoformat(),
    "submission_close_datetime": datetime.now().isoformat(),
    "customer_json": {"name": "Customer", "inn": "1234567890"},
    "contact_json": {"email": "test@test.com", "phone": "+71234567890"},
    "apply_request_json": {"status": "open", "requests": 5},
    "lot": {"number": 1, "description": "Main lot"}
})

print(f"Status: {response.status_code}")
pprint(response.json())

# 2. POST /get_purchase - Получить закупку
print("\n" + "="*50)
print("2. Getting purchase...")
response = requests.post(f"{APP_URL}/get_purchase", json={
    "token": SYSTEM_TOKEN,
    "guid": "123"
})

print(f"Status: {response.status_code}")
pprint(response.json())

# 3. PUT /update_purchase - Обновить закупку
print("\n" + "="*50)
print("3. Updating purchase...")
response = requests.put(f"{APP_URL}/update_purchase", json={
    "token": SYSTEM_TOKEN,
    "guid": "123",
    "name": "Обновленная тестовая закупка",
    "initial_sum": 2000.0
})

print(f"Status: {response.status_code}")
pprint(response.json())

# 4. POST /get_all_purchases - Получить список с фильтрами
print("\n" + "="*50)
print("4. Getting all purchases with filters...")
response = requests.post(f"{APP_URL}/get_all_purchases", json={
    "token": SYSTEM_TOKEN,
    "name": "тестовая",
    "initial_sum_from": 500,
    "initial_sum_to": 5000
})

print(f"Status: {response.status_code}")
pprint(response.json())

# 5. GET /stats - Статистика
print("\n" + "="*50)
print("5. Getting statistics...")
response = requests.get(f"{APP_URL}/stats")

print(f"Status: {response.status_code}")
pprint(response.json())

# 6. GET /health - Проверка здоровья
print("\n" + "="*50)
print("6. Health check...")
response = requests.get(f"{APP_URL}/health")

print(f"Status: {response.status_code}")
pprint(response.json())

# 7. DELETE /delete_purchase - Удалить закупку
print("\n" + "="*50)
print("7. Deleting purchase...")
response = requests.delete(f"{APP_URL}/delete_purchase", json={
    "token": SYSTEM_TOKEN,
    "guid": "123"
})

print(f"Status: {response.status_code}")
pprint(response.json())