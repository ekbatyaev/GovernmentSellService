# GovernmentSellService

Сервис для автоматического сбора, фильтрации, хранения и рассылки данных о закупках по 223-ФЗ с портала [zakupki.gov.ru](https://zakupki.gov.ru).

Бэкенд на FastAPI ежедневно опрашивает SOAP-интеграцию портала госзакупок по всем регионам РФ, скачивает XML-архивы извещений и протоколов, прогоняет их через фильтры под три направления (Россети, OEM, ITM), с помощью YandexGPT (Yandex Cloud) извлекает данные из протоколов и приложенных документов (PDF/DOCX/XLSX, включая OCR), сохраняет закупки в PostgreSQL и рассылает подписчикам email с Excel-отчётом. Поверх API есть веб-интерфейс на React для просмотра, фильтрации и администрирования закупок.

## Возможности

- ежедневный импорт извещений и протоколов закупок по расписанию (APScheduler, cron по МСК);
- backfill за N дней назад при старте контейнера или по запросу через админ-API;
- обход всех регионов РФ через SOAP-интеграцию портала госзакупок (`RI223`);
- фильтрация закупок по трём направлениям: «Тендеры для Россетей», «Тендеры для OEM», «Тендеры для ITM» — каждое со своим набором regex-фильтров по заказчику/наименованию и своим списком регионов;
- скачивание и разбор вложений закупок (PDF, DOCX, XLSX, ZIP/RAR-архивы, в т.ч. многотомные RAR) с OCR первой страницы PDF при отсутствии текстового слоя;
- извлечение структурированных данных из протоколов через YandexGPT (отдельный экстрактор под каждое направление, доступ через OpenAI-совместимый API Yandex Cloud);
- хранение закупок и подписчиков в PostgreSQL (JSONB для вложенных структур, массивы для лотов и списка документов);
- REST API для CRUD-операций над закупками и подписками рассылки;
- защита служебных и админ-эндпоинтов системным токеном;
- защита фоновых задач от параллельного запуска через PostgreSQL advisory lock;
- автоматическое удаление закупок с истёкшим сроком подачи заявок и закупок старше года;
- подписка/отписка от рассылки с подтверждением email через одноразовый код;
- формирование и отправка Excel-отчёта по новым/обновлённым закупкам через Exchange Web Services (EWS);
- веб-интерфейс (React + Vite + TypeScript): дашборд, таблица закупок с фильтрами и поиском, управление рассылкой, админ-панель для ручного запуска фоновых задач.

## Архитектура проекта

```text
.
├── app
│   ├── database
│   │   ├── main.py                     # FastAPI: роуты, Pydantic-модели, планировщик
│   │   ├── scheduler.py                # Ежедневный джоб, backfill, формирование и отправка отчётов
│   │   ├── connection_to_database.py   # SQLAlchemy engine/session, advisory lock
│   │   ├── table_models.py             # ORM-модели Purchase и NewsLetter
│   │   └── email_handles.py            # Отправка писем через Exchange Web Services
│   ├── goszakupki_requests
│   │   ├── xml_archives_request.py     # SOAP-запросы к порталу, скачивание архивов
│   │   ├── parse_xml_archive_223fz.py  # Разбор XML извещений/протоколов 223-ФЗ, применение фильтров
│   │   ├── get_documents_consistent.py # Скачивание и парсинг вложений (PDF/DOCX/XLSX/ZIP/RAR), OCR
│   │   ├── filters/
│   │   │   ├── rosseti_filters.py      # Regex-фильтры под направление «Россети»
│   │   │   ├── oem_filters.py          # Regex-фильтры под направление «OEM»
│   │   │   └── itm_filters.py          # Regex-фильтры под направление «ITM»
│   │   └── ai_requests/
│   │       ├── rosseti_protocol_extractor.py  # Извлечение полей протокола через YandexGPT (Россети)
│   │       ├── oem_protocol_extractor.py      # То же для OEM
│   │       └── itm_protocol_extractor.py      # То же для ITM
│   └── static_legacy/                  # Старая статика (index.html/script.js/style.css), заменена на frontend
├── frontend/                           # React + TypeScript + Vite SPA
│   ├── src/
│   │   ├── pages/                      # DashboardPage, PurchasesPage, NewsletterPage, AdminPage
│   │   ├── components/                 # layout (AppShell, Header, Sidebar) и ui-примитивы
│   │   ├── api/                        # клиент API, работа с закупками и статистикой
│   │   ├── lib/                        # форматирование, вспомогательная логика
│   │   └── types/                      # типы Purchase и API-моделей
│   └── package.json
├── tests/
│   ├── get_doc_by_reestr_num.py        # Скрипт для отладки: скачать закупку по номеру напрямую с портала
│   └── pipeline_test.py                # Ручной прогон пайплайна получения и парсинга закупок
├── Dockerfile                          # Многоступенчатая сборка: frontend (Vite build) → backend (Python)
├── docker-compose.yml                  # Сервисы app + PostgreSQL
└── requirements.txt
```

> Примечание: `app/static_legacy` — предыдущая версия статического интерфейса, оставлена в репозитории для истории. В продакшене FastAPI отдаёт собранный из `frontend/` бандл (см. Dockerfile).

## Как это работает

1. При старте FastAPI инициализирует таблицы в PostgreSQL и планировщик APScheduler.
2. Если включён `PIPELINE_BACKFILL_ON_STARTUP`, выполняется backfill за `BACKFILL_DAYS` последних дней.
3. Ежедневно по cron (`DAILY_JOB_HOUR_MSK` / `DAILY_JOB_MINUTE_MSK`, таймзона Europe/Moscow) запускается основной джоб за вчерашний день.
4. Для каждого из ~90 регионов РФ джоб запрашивает через SOAP-интеграцию портала извещения (`purchaseNotice`) и протоколы (`purchaseProtocol`) по 223-ФЗ и скачивает XML-архивы.
5. Архивы извещений разбираются, прогоняются через regex-фильтры трёх направлений (Россети/OEM/ITM); прошедшие фильтр закупки сохраняются в БД через внутренний API.
6. Архивы протоколов разбираются, вложенные документы скачиваются и парсятся (PDF/DOCX/XLSX/ZIP/RAR, с OCR при необходимости), извлечённые данные обогащаются через YandexGPT и записываются в существующую закупку (или создают новую, если извещения не было).
7. Закупки старше года и закупки с истёкшим сроком подачи заявок удаляются.
8. По каждому направлению и региону/федеральному округу формируется Excel-отчёт и рассылается подписчикам письмом через Exchange Web Services.
9. Статус последней фоновой задачи доступен через `/admin/job_status`, ручной запуск — через `/admin/run_daily`, `/admin/run_backfill`, `/admin/run_process_day`, `/admin/run_backfill_period_of_time`.

## Технологии

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL 16, APScheduler, requests, lxml / xmltodict, pandas / openpyxl, python-docx, pypdf, PyMuPDF, pytesseract (OCR), rarfile, natasha / pymorphy2 (обработка русского текста), YandexGPT (Yandex Cloud, через openai-совместимый SDK), exchangelib (EWS для отправки почты).

**Frontend:** React 19, TypeScript, Vite, TanStack Query, React Router, Tailwind CSS 4, lucide-react, exceljs / xlsx (экспорт в Excel на клиенте).

**Инфраструктура:** Docker, Docker Compose (многоступенчатая сборка: сначала собирается frontend, затем его `dist` копируется в образ backend).

## Модель данных

### `purchases`

Основная таблица закупок.

Ключевые поля: `guid` (первичный ключ), `registration_number` (реестровый номер), `name`, `initial_sum`, `publication_datetime`, `submission_start_datetime`, `submission_close_datetime`, `customer` (JSONB), `contact` (JSONB), `apply_request` (JSONB), `result_info` (JSONB — данные протокола, извлечённые ИИ), `documents_list` (массив путей к вложениям), `lots` (массив JSONB с лотами и позициями), `filter_type_name` (направление: Россети/OEM/ITM), `region_number`, `source_file` (исходный XML-файл).

### `newsletter`

Подписчики рассылки: `id`, `email`, `filter_type_name`, `district_name`. Уникальность — по паре (email, filter_type_name, district_name), то есть один email может быть подписан на несколько направлений/округов.

## API

Все служебные и админ-эндпоинты защищены системным токеном (передаётся полем `token` в теле запроса).

### Публичные/служебные GET

- `GET {API_BASE}/` — веб-интерфейс;
- `GET {API_BASE}/config` — конфигурация клиента;
- `GET {API_BASE}/stats` — статистика (кол-во закупок, подписчиков, время последних задач);
- `GET {API_BASE}/health` — healthcheck БД;
- `GET {API_BASE}/admin/job_status` — статус последней фоновой задачи (без токена).

### Закупки

- `POST {API_BASE}/put_purchase` — создать/обновить закупку;
- `POST {API_BASE}/get_purchase` — получить одну закупку по guid или реестровому номеру;
- `POST {API_BASE}/get_all_purchases` — список с фильтрами (название, сумма, даты публикации/подачи, регион(ы), направление, признак OEM);
- `POST {API_BASE}/update_purchase` — частичное обновление;
- `POST {API_BASE}/delete_purchase` — удаление по guid.

### Администрирование

- `POST {API_BASE}/admin/run_daily` — ручной запуск ежедневного джоба;
- `POST {API_BASE}/admin/run_process_day` — обработать конкретную дату;
- `POST {API_BASE}/admin/run_backfill` — backfill за N дней;
- `POST {API_BASE}/admin/run_backfill_period_of_time` — обработать диапазон дат;
- `POST {API_BASE}/admin/delete_expired` — удалить закупки с истёкшим сроком подачи.

### Рассылка

- `POST {API_BASE}/put_newsletter` / `delete_newsletter` / `get_newsletter` / `get_all_newsletters`;
- `POST {API_BASE}/send_auth_code` — отправить одноразовый код подтверждения на email;
- `POST {API_BASE}/verify_code` — подтвердить код.

## Веб-интерфейс

SPA на React с четырьмя разделами: `DashboardPage` (сводная статистика), `PurchasesPage` (таблица закупок с поиском, фильтрами и экспортом в Excel), `NewsletterPage` (подписка/отписка от рассылки с подтверждением по email-коду), `AdminPage` (ручной запуск фоновых задач и просмотр статуса). Собирается через Vite и на этапе сборки Docker-образа копируется в `static/` бэкенда.

## Настройка окружения

Создайте файл `.env` в корне проекта:

```env
# PostgreSQL
POSTGRES_DB=goszakupki
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=db
POSTGRES_PORT=5432

# FastAPI
APP_HOST=0.0.0.0
APP_PORT=8000
APP_URL=http://127.0.0.1:8000
API_BASE=

# SOAP-интеграция портала госзакупок
BASE_URL=
DOWNLOAD_URL=
TOKEN=
SOAP_TIMEOUT=90
DOWNLOAD_TIMEOUT=90

# Системный токен для служебных/админ-эндпоинтов
SYSTEM_TOKEN=

# Backfill / расписание / повторные попытки
PIPELINE_BACKFILL_ON_STARTUP=false
BACKFILL_DAYS=7
DAILY_JOB_HOUR_MSK=10
DAILY_JOB_MINUTE_MSK=0
SCHEDULER_LOCK_KEY=424242
RETRY_COUNT=3
RETRY_DELAY=10

# Email / Exchange Web Services
SMTP_SERVER=
SMTP_PORT=
SMTP_USER=
SMTP_EMAIL=
SMTP_PASSWORD=
SMTP_TEST_EMAIL=

# YandexGPT (извлечение данных из протоколов)
YANDEX_CLOUD_MODEL=
YANDEX_CLOUD_FOLDER=
YANDEX_CLOUD_API_KEY=
```

Примечания по отдельным переменным:

- `API_BASE` — префикс путей API и статики (например, `/goszakupki`); используется и бэкендом, и вызовами планировщика к самому себе через `APP_URL`.
- `TOKEN` — токен доступа к SOAP-интеграции портала госзакупок (`BASE_URL`), не путать с `SYSTEM_TOKEN`, который защищает собственные эндпоинты сервиса.
- `PIPELINE_BACKFILL_ON_STARTUP` — именно под таким именем читается флагом backfill при старте контейнера (в `app/database/scheduler.py`).
- `YANDEX_CLOUD_MODEL` — алиас модели (например, `yandexgpt`), подставляется в идентификатор модели вида `gpt://{YANDEX_CLOUD_FOLDER}/{YANDEX_CLOUD_MODEL}`.

## Запуск через Docker Compose

```bash
docker compose up --build
```

По умолчанию приложение публикуется на порту `8002`, PostgreSQL — на `5434`. После запуска интерфейс доступен по адресу:

```
http://localhost:8002/goszakupki/
```

## Локальная разработка frontend

```bash
cd frontend
npm install
npm run dev
```

## Тесты / отладочные скрипты

В `tests/` лежат не автотесты, а ручные скрипты для отладки интеграции с порталом госзакупок:

- `get_doc_by_reestr_num.py` — скачать и разобрать конкретную закупку по реестровому номеру напрямую с портала, в обход БД;
- `pipeline_test.py` — прогнать пайплайн получения и парсинга закупок за произвольный период без записи в прод-БД.

## Лицензия

MIT, см. [LICENSE](LICENSE).
