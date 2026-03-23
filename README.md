# GovernmentSellService

GovernmentSellService — сервис для автоматического сбора, хранения, фильтрации и рассылки данных о государственных закупках.

Проект поднимает API и веб-интерфейс для просмотра закупок, сохраняет данные в PostgreSQL, по расписанию забирает новые документы из внешнего SOAP-сервиса, парсит XML-архивы, сохраняет подходящие закупки в базу и отправляет подписчикам email-уведомления с Excel-отчётом.

## Возможности

- автоматический ежедневный импорт закупок по расписанию;
- backfill за несколько предыдущих дней при старте или вручную;
- хранение закупок в PostgreSQL;
- REST API для работы с закупками;
- веб-интерфейс для просмотра и фильтрации закупок;
- подписка и отписка от email-рассылки;
- подтверждение email через код;
- отправка Excel-отчёта по новым закупкам;
- защита служебных API через системный токен;
- защита фоновых задач от параллельного запуска через PostgreSQL advisory lock.

## Архитектура проекта

```text
.
├── app
│   ├── database
│   │   ├── main.py
│   │   ├── scheduler.py
│   │   ├── connection_to_database.py
│   │   ├── table_models.py
│   │   └── email_handles.py
│   ├── goszakupki_requests
│   │   ├── data_request.py
│   │   ├── document_consistent.py
│   │   ├── parse_data_fz_223.py
│   │   └── parse_data_fz_44.py
│   └── static
│       ├── index.html
│       ├── script.js
│       └── style.css
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

## Как это работает
	1.	Приложение запускает FastAPI и инициализирует базу данных.
	2.	На старте может выполняться backfill за последние несколько дней.
	3.	APScheduler запускает ежедневную задачу по cron.
	4.	Фоновая задача обращается к внешнему SOAP API, получает архив документов и скачивает XML.
	5.	Парсер нормализует данные закупок и сохраняет их в PostgreSQL.
	6.	После импорта формируется Excel-отчёт по новым закупкам.
	7.	Подписчики получают письмо с количеством новых закупок и вложенным файлом.

## Технологии
	•	Python 3.12
	•	FastAPI
	•	PostgreSQL
	•	SQLAlchemy
	•	APScheduler
	•	requests
	•	lxml / xmltodict
	•	pandas / openpyxl
	•	exchangelib для отправки почты через Exchange Web Services
	•	Docker / Docker Compose

## Модель данных

### purchases

Основная таблица закупок.

Ключевые поля:

	•	guid — первичный ключ закупки;
	•	registration_number — регистрационный номер;
	•	name — название закупки;
	•	initial_sum — сумма;
	•	publication_datetime — дата публикации;
	•	submission_close_datetime — дедлайн подачи;
	•	customer — JSONB с данными заказчика;
	•	contact — JSONB с контактной информацией;
	•	apply_request — JSONB с данными подачи;
	•	lots — массив JSONB с лотами и позициями;
	•	created_at — дата добавления в систему;
	•	source_file — исходный XML-файл.

### newsletter

Таблица подписчиков рассылки.

Поля:

	•	id
	•	email

## API

Ниже перечислены основные маршруты. Все служебные POST-эндпоинты используют системный токен.

### Публичные/служебные GET
	•	GET {API_BASE}/ — веб-интерфейс
	•	GET {API_BASE}/config — конфигурация клиента
	•	GET {API_BASE}/stats — статистика
	•	GET {API_BASE}/health — healthcheck
	•	GET {API_BASE}/admin/job_status — статус последней фоновой задачи

### Закупки
	•	POST {API_BASE}/put_purchase
	•	POST {API_BASE}/get_purchase
	•	POST {API_BASE}/get_all_purchases
	•	POST {API_BASE}/update_purchase
	•	POST {API_BASE}/delete_purchase

### Поддерживаются фильтры по:
	•	названию;
	•	сумме;
	•	дате публикации;
	•	сроку окончания подачи;
	•	дате создания записи;
	•	имени исходного файла.

### Администрирование
	•	POST {API_BASE}/admin/run_daily
	•	POST {API_BASE}/admin/run_process_day
	•	POST {API_BASE}/admin/run_backfill
	•	POST {API_BASE}/admin/delete_expired

### Рассылка
	•	POST {API_BASE}/put_newsletter
	•	POST {API_BASE}/delete_newsletter
	•	POST {API_BASE}/get_newsletter
	•	POST {API_BASE}/get_all_newsletters
	•	POST {API_BASE}/send_auth_code
	•	POST {API_BASE}/verify_code

## Веб-интерфейс

Во фронтенде есть:
	•	табличный и карточный режим просмотра;
	•	клиентская фильтрация по статусу дедлайна;
	•	поиск;
	•	сортировка;
	•	пагинация;
	•	сохранение состояния фильтров в URL;
	•	подписка/отписка через email-код;
	•	экспорт данных.

Интерфейс расположен в app/static.

## Настройка окружения

Создайте файл .env в корне проекта.

```text
# FastAPI
SYSTEM_TOKEN=your_system_token
API_BASE=/goszakupki

# Scheduler
DAILY_JOB_HOUR_MSK=10
DAILY_JOB_MINUTE_MSK=0

# Backfill
BACKFILL_ON_STARTUP=true
BACKFILL_DAYS=7
RETRY_COUNT=3
RETRY_DELAY=10
EXPIRE_MODE=now

# PostgreSQL
POSTGRES_DB=goszakupki
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432

# External SOAP service
BASE_URL=https://example.com/soap
TOKEN=external_service_token
DOWNLOAD_URL=https://example.com/download
SOAP_TIMEOUT=30
DOWNLOAD_TIMEOUT=60
TMP_DIR=tmp

# Email / EWS
SMTP_SERVER=...
SMTP_PORT=...
SMTP_USER=...
SMTP_EMAIL=...
SMTP_PASSWORD=...
SMTP_TEST_EMAIL=...

```

## Запуск через Docker Compose

```
docker compose up --build
```

По умолчанию:
	•	приложение публикуется на 8002;
	•	PostgreSQL публикуется на 5434.

После запуска интерфейс будет доступен по адресу:
```
http://localhost:8002/goszakupki/
```
