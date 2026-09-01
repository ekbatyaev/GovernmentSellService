# GovernmentSellService

Сервис для автоматического сбора, фильтрации и рассылки закупок по 223-ФЗ с портала [zakupki.gov.ru](https://zakupki.gov.ru).

Каждый день бэкенд опрашивает SOAP-интеграцию портала по всем регионам РФ, скачивает XML-архивы извещений и протоколов, прогоняет их через фильтры трёх направлений, извлекает данные из протоколов и приложенных документов через YandexGPT, сохраняет закупки в PostgreSQL и рассылает подписчикам письма с отчётом. Поверх — веб-интерфейс на React для просмотра и администрирования.

## Возможности

- ежедневный импорт извещений и протоколов по расписанию (APScheduler, cron по МСК) + ручной backfill за N дней;
- обход всех регионов РФ через SOAP-интеграцию портала (`RI223`);
- три направления фильтрации — «Россети», «OEM», «ITM» — каждое со своим набором regex-фильтров и списком регионов;
- разбор вложений закупок (PDF, DOCX, XLSX, ZIP/RAR, включая многотомные) с OCR для сканов без текстового слоя;
- извлечение структурированных данных из протоколов через YandexGPT — отдельный экстрактор под каждое направление;
- хранение закупок и подписчиков в PostgreSQL;
- REST API для закупок и подписок, защищённый системным токеном;
- защита фоновых задач от параллельного запуска через PostgreSQL advisory lock;
- подписка/отписка от рассылки с подтверждением email-кодом;
- отправка Excel-отчётов по новым/обновлённым закупкам через Exchange Web Services;
- веб-интерфейс (React + Vite + TypeScript): дашборд, таблица закупок, управление рассылкой, админ-панель.

## Архитектура

```
app/
├── main.py                 # точка входа FastAPI: lifespan (БД + планировщик), статика фронтенда
├── routers.py               # все HTTP-роуты
├── settings.py               # конфигурация (pydantic-settings), логирование
├── backend/
│   ├── api_client.py         # внутренний HTTP-клиент к собственному API
│   ├── functions.py          # пайплайн дня: обход регионов, сохранение закупок/протоколов
│   ├── models.py             # Pydantic-модели запросов и ответов
│   ├── scheduler.py          # APScheduler: ежедневный джоб, backfill, формирование и отправка отчётов
│   ├── db/
│   │   ├── settings.py        # SQLAlchemy engine/session, advisory lock
│   │   ├── table_models.py    # ORM: Purchase, NewsLetter, AuthCode
│   │   └── static_info.py     # справочники регионов и федеральных округов
│   ├── email/
│   │   └── functions.py       # отправка писем через Exchange Web Services
│   ├── ai/
│   │   ├── client.py          # клиент YandexGPT (OpenAI-совместимый API)
│   │   └── functions/         # экстракторы протоколов под Россети/OEM/ITM
│   └── parsers/
│       ├── request_archives.py # SOAP-запросы к порталу, скачивание архивов
│       ├── xml_parser.py       # разбор XML извещений и протоколов 223-ФЗ
│       ├── doc_parser.py       # парсинг вложений (PDF/DOCX/XLSX/RAR), OCR
│       └── filters/            # regex-фильтры трёх направлений
└── frontend/                 # React + TypeScript + Vite SPA
    └── src/
        ├── pages/              # DashboardPage, PurchasesPage, NewsletterPage, AdminPage
        ├── components/         # layout и UI-примитивы
        ├── api/, lib/, types/  # клиент API, форматирование, типы
```

## Как это работает

1. При старте FastAPI создаёт таблицы в PostgreSQL и запускает планировщик.
2. Если включён `BACKFILL_ON_STARTUP` — выполняется backfill за `BACKFILL_DAYS` дней.
3. Ежедневно по cron (`DAILY_JOB_HOUR_MSK` / `DAILY_JOB_MINUTE_MSK`, Europe/Moscow) запускается основной джоб за вчерашний день.
4. Для каждого региона джоб запрашивает через SOAP извещения и протоколы по 223-ФЗ и скачивает XML-архивы.
5. Извещения разбираются и прогоняются через фильтры трёх направлений; прошедшие фильтр закупки сохраняются через внутренний API.
6. Протоколы разбираются, вложения скачиваются и парсятся, данные обогащаются через YandexGPT и записываются в закупку (или создают новую, если извещения не было).
7. Закупки старше года удаляются.
8. По каждому направлению и региону формируется отчёт и рассылается подписчикам письмом.

## Технологии

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), PostgreSQL 16, APScheduler, httpx, lxml / xmltodict, pandas / openpyxl, python-docx, kreuzberg, rarfile, tesseract (OCR), YandexGPT через `openai`-совместимый SDK, exchangelib (EWS).

**Frontend:** React 19, TypeScript, Vite, TanStack Query, React Router, Tailwind CSS 4, exceljs / xlsx.

**Инфраструктура:** Docker / Docker Compose — многоступенчатая сборка (сначала frontend через Vite, затем его `dist` копируется в образ backend).

## Данные

**`purchases`** — закупки. `guid` (первичный ключ, стабилен на всё время жизни записи), `registration_number`, `name`, `initial_sum`, даты публикации/подачи, `customer` / `contact` / `apply_request` / `result_info` (JSONB), `documents_list`, `lots`, `filter_type_name`, `region_number`.

**`newsletter`** — подписчики: `email`, `filter_type_name`, `district_name`, с уникальностью по этой тройке.

## API

Все эндпоинты, кроме публичных GET, защищены системным токеном (`token` в теле запроса).

| Группа | Эндпоинты |
|---|---|
| Закупки | `put_purchase`, `get_purchase`, `get_all_purchases`, `update_purchase`, `delete_purchase` |
| Рассылка | `put_newsletter`, `delete_newsletter`, `get_newsletter`, `get_all_newsletters`, `send_auth_code`, `verify_code` |
| Администрирование | `admin/run_process_day`, `admin/run_backfill`, `admin/run_backfill_period_of_time`, `admin/delete_expired`, `admin/job_status` |
| Служебные GET | `/`, `config`, `stats`, `health` |

## Конфигурация

Переменные окружения (см. `.env.example`):

```env
# PostgreSQL
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=db
POSTGRES_PORT=5432

# FastAPI
APP_URL=http://127.0.0.1:8000
APP_BASE=

# SOAP-интеграция портала госзакупок
BASE_URL=https://int.zakupki.gov.ru/eis-integration/services/getDocsIP
DOWNLOAD_URL=https://int.zakupki.gov.ru/dstore/common/download/compound
TOKEN=
SOAP_TIMEOUT=90
DOWNLOAD_TIMEOUT=90

# Системный токен собственного API
SYSTEM_TOKEN=

# Расписание / backfill / повторные попытки
BACKFILL_ON_STARTUP=false
BACKFILL_DAYS=7
DAILY_JOB_HOUR_MSK=10
DAILY_JOB_MINUTE_MSK=0
SCHEDULER_LOCK_KEY=424242
RETRY_COUNT=3
RETRY_DELAY=10
MAX_CONCURRENT_SEMAPHORE=5
TMP_DIR=tmp

# Email (Exchange Web Services)
SMTP_SERVER=
SMTP_PORT=
SMTP_USER=
SMTP_EMAIL=
SMTP_PASSWORD=
SMTP_TEST_EMAIL=

# YandexGPT
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL_NAME=
LLM_FOLDER_ID=
```

`TOKEN` — доступ к SOAP-интеграции портала, не путать с `SYSTEM_TOKEN` — им защищены собственные эндпоинты сервиса.

## Запуск

```bash
docker compose up --build
```

Приложение публикуется на `http://localhost:8002`, PostgreSQL — на порту `5434`.

## Локальная разработка фронтенда

```bash
cd app/frontend
npm install
npm run dev
```

## Лицензия

MIT, см. [LICENSE](LICENSE).
