import requests
from pprint import pprint

BASE_URL = "http://127.0.0.1:8000"

USERNAME = "testuser"
PASSWORD = "password123"

def main():
    print("\n=== Регистрация пользователя ===")
    register_payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    resp = requests.post(f"{BASE_URL}/user_register", json=register_payload)
    pprint(resp.json())

    headers = {
        "username": USERNAME,
        "password": PASSWORD
    }

    print("\n=== Логин пользователя ===")
    login_payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    resp = requests.post(f"{BASE_URL}/user_login", json=login_payload)
    pprint(resp.json())

    print("\n=== Получить информацию о себе ===")
    resp = requests.get(f"{BASE_URL}/users/info", headers=headers)
    pprint(resp.json())

    print("\n=== Создать тему ===")
    topic_payload = {
        "title": "Python Basics",
        "description": "Learn Python from scratch",
        "data_json": {"lessons": 5, "difficulty": "easy"}
    }
    resp = requests.post(f"{BASE_URL}/create_topic", json=topic_payload, headers=headers)
    topic = resp.json()
    pprint(topic)
    topic_id = topic["id"]

    print("\n=== Получить все темы ===")
    resp = requests.get(f"{BASE_URL}/topics")
    pprint(resp.json())

    print("\n=== Получить тему по ID ===")
    resp = requests.get(f"{BASE_URL}/topics/get_info_{topic_id}")
    pprint(resp.json())

    print("\n=== Обновить тему ===")
    update_payload = {
        "title": "Python Basics Updated",
        "description": "Updated description",
    }

    resp = requests.put(f"{BASE_URL}/topics/update_{topic_id}", json=update_payload, headers=headers)
    pprint(resp.json())

    print("\n=== Получить свои темы ===")
    resp = requests.get(f"{BASE_URL}/users/me/topics", headers=headers)
    pprint(resp.json())

    print("\n=== Удалить тему ===")
    resp = requests.delete(f"{BASE_URL}/topics/delete_{topic_id}", headers=headers)
    pprint(resp.json())

    print("\n=== Получить свои темы ===")
    resp = requests.get(f"{BASE_URL}/users/me/topics", headers=headers)
    pprint(resp.json())

    print("\n=== Статистика ===")
    resp = requests.get(f"{BASE_URL}/stats")
    pprint(resp.json())

    print("\n=== Проверка здоровья ===")
    resp = requests.get(f"{BASE_URL}/health")
    pprint(resp.json())


if __name__ == "__main__":
    main()