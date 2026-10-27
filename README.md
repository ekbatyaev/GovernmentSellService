# GovernmentSellService

Сервис для автоматического сбора, фильтрации и рассылки закупок по 223-ФЗ с портала [zakupki.gov.ru](https://zakupki.gov.ru).

Каждый день бэкенд опрашивает SOAP-интеграцию портала по всем регионам РФ, скачивает XML-архивы извещений и протоколов, прогоняет их через фильтры трёх направлений, извлекает данные из приложенных документов (в том числе через YandexGPT), сохраняет закупки в PostgreSQL и рассылает подписчикам письма с Excel-отчётом. Поверх — веб-интерфейс на React с авторизацией пользователей.

## Возможности

- ежедневный импорт извещений и протоколов по расписанию (APScheduler, cron по МСК) и ручной запуск за день или период из админ-панели;
- обход всех регионов РФ через SOAP-интеграцию портала (`RI223`) с ограничением параллельности по регионам, архивам и записям;
- три направления фильтрации — «Тендеры для Россетей», «Тендеры для OEM», «Тендеры для ITM» — со своими regex-фильтрами и списками регионов;
- разбор вложений закупок (PDF, DOC/DOCX, XLSX, RTF, ZIP/RAR, включая многотомные RAR) с OCR для сканов без текстового слоя;
- извлечение структурированных данных из протоколов через YandexGPT — отдельный экстрактор под каждое направление;
- пользователи с ролями `guest` / `user` / `admin`: регистрация с кодом из письма, подтверждение администратором, вход по JWT;
- подписка и отписка от рассылки с подтверждением email-кодом;
- Excel-отчёты по новым и обновлённым закупкам, отправка через Exchange Web Services;
- автоочистка: закупки старше 6 месяцев и просроченные коды подтверждения удаляются ежедневным джобом;
- веб-интерфейс (React + Vite + TypeScript): дашборд, закупки с фильтрами и редактированием, рассылка, админ-панель, вход и регистрация.

## Архитектура

```
app/
├── main.py                    # точка входа FastAPI: lifespan (БД, админ, планировщик), роутеры, раздача фронтенда
├── settings.py                # конфигурация (pydantic-settings), логирование
├── routers/
│   ├── dependencies.py        # JWT, хеширование паролей, get_current_user / require_admin
│   ├── schemas.py             # общий ResponseModel
│   ├── users/                 # регистрация, вход, подтверждение, управление пользователями
│   ├── purchases/             # CRUD и поиск закупок
│   ├── newsletters/           # CRUD и подтверждение подписок
│   └── services/              # статистика, статус задач, запуск пайплайна, отправка кодов
├── schemas/                   # Pydantic-схемы: purchase, newsletter, user, service
├── backend/
│   ├── constraints.py         # справочники регионов, федеральных округов и регионов фильтров
│   ├── database/
│   │   ├── settings.py        # SQLAlchemy engine/session, advisory lock
│   │   ├── models.py          # ORM: purchases, newsletter, users, auth_codes
│   │   ├── functions.py       # создание администратора при старте
│   │   └── crud/              # purchase, newsletter, user, service (коды подтверждения)
│   ├── functions/
│   │   ├── notices/           # пайплайн дня: обход регионов (process.py), сохранение записей (record.py)
│   │   ├── analysis.py        # формирование Excel-отчётов и рассылка
│   │   └── tasks.py           # фоновые задачи админ-панели и их статус
│   ├── scheduler/             # APScheduler: ежедневный джоб, очистка, рассылка по подписчикам
│   ├── email/functions.py     # отправка писем через Exchange Web Services
│   ├── ai/
│   │   ├── client.py          # клиент YandexGPT (OpenAI-совместимый API)
│   │   └── functions/         # экстракторы протоколов под Россети / OEM / ITM
│   └── parsers/
│       ├── request_archives.py # SOAP-запросы к порталу, скачивание архивов
│       ├── xml_parser.py       # разбор XML извещений и протоколов 223-ФЗ
│       ├── doc_parser.py       # скачивание и парсинг вложений, OCR, слияние результатов
│       └── filters/            # regex-фильтры трёх направлений
└── frontend/                   # React + TypeScript + Vite SPA
    └── src/
        ├── auth/               # хранение JWT, контекст авторизации, автовыход
        ├── api/                # клиент API (Bearer-токен, обработка ошибок)
        ├── pages/              # Auth, Approve, Dashboard, Purchases, Newsletter, Admin
        ├── components/         # layout и UI-примитивы
        └── lib/, types/        # форматирование, справочники, типы
```

## Как это работает

1. При старте FastAPI создаёт таблицы в PostgreSQL, создаёт администратора из `SUPERVISOR_SYSTEM_EMAIL` / `SUPERVISOR_SYSTEM_PASSWORD` (если его ещё нет) и запускает планировщик.
2. Ежедневно по cron (`DAILY_JOB_HOUR_MSK` / `DAILY_JOB_MINUTE_MSK`, Europe/Moscow) запускается основной джоб за вчерашний день.
3. Для каждого региона джоб запрашивает через SOAP извещения и протоколы по 223-ФЗ и скачивает XML-архивы.
4. Извещения разбираются и прогоняются через фильтры трёх направлений. Для прошедших скачиваются и разбираются вложения, закупка сохраняется в БД (новая создаётся, существующая обновляется).
5. Протоколы разбираются так же, данные из вложений и YandexGPT дописываются в уже сохранённую закупку.
6. Закупки старше 6 месяцев и просроченные коды подтверждения удаляются.
7. По каждому направлению и региону/округу формируется Excel-отчёт и рассылается подписчикам.

Тот же пайплайн можно запустить вручную из админ-панели — за конкретный день или за период, с выбором направления.

## Пользователи и доступ

Все эндпоинты, кроме входа и регистрации, требуют JWT в заголовке `Authorization: Bearer <token>`. Токен живёт `JWT_EXPIRE_MINUTES` минут, фронтенд хранит его в `localStorage` и выходит на экран входа при истечении.

Регистрация:
1. `POST /users/confirm` — код подтверждения на почту;
2. `POST /users/register/{guid}` — код + пароль, пользователь создаётся с ролью `guest`;
3. администратору (`SUPERVISOR_SYSTEM_EMAIL`) приходит письмо со ссылкой `/approve/{guid}`, где он назначает роль `user` или `admin`;
4. пользователю приходит письмо о подтверждении — после этого можно войти.

Пока роль `guest`, вход проходит, но защищённые эндпоинты отвечают 401.

## API

Документация Swagger — `http://localhost:8002/docs`.

| Группа | Эндпоинты |
|---|---|
| Пользователи | `POST /users/login`, `POST /users/confirm`, `POST /users/register/{guid}`, `POST /users/approve/{guid}` (admin), `GET` / `PATCH` / `DELETE /users/{guid}` |
| Закупки | `POST /purchases`, `POST /purchases/search`, `GET` / `PATCH` / `DELETE /purchases/{guid}` |
| Рассылка | `POST /newsletters`, `POST /newsletters/search`, `POST /newsletters/confirm`, `GET` / `PATCH` / `DELETE /newsletters/{guid}` |
| Сервис | `GET /services/health`, `GET /services/stats`, `GET /services/stats/job_status`, `POST /services/send_auth_code/{email}`, `POST /services/run/process_day`, `POST /services/run/process_period` |

Ответы имеют вид `{"status_message": "...", "data": ...}`, ошибки — `{"detail": "..."}`.

`filter_number` в запуске пайплайна: `0` — все направления, `1` — Россети, `2` — OEM, `3` — ITM.

## Данные

- **`purchases`** — закупки: `guid` (первичный ключ), `registration_number`, `name`, `initial_sum`, даты публикации и подачи, `customer` / `contact` / `apply_request` / `result_info` (JSONB), `documents_list`, `lots`, `filter_type_name`, `region_number`, `source_file`.
- **`newsletter`** — подписки: `email`, `filter_type_name`, `district_name` (код региона для Россетей, федеральный округ для OEM/ITM), уникальность по этой тройке.
- **`users`** — пользователи: `email` (уникальный), хеш пароля (argon2), `role`, `created_at`.
- **`auth_codes`** — одноразовые коды подтверждения для регистрации и рассылки.

## Конфигурация

Переменные окружения (шаблон — `.env.example`):

```env
# PostgreSQL
POSTGRES_DB=goszakupki
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Приложение
APP_URL=http://127.0.0.1:8000
APP_WEB_OPEN_URL=http://127.0.0.1:8002   # база для ссылок в письмах (/approve/{guid})
JWT_SECRET=                              # длинная случайная строка
JWT_EXPIRE_MINUTES=60

# Администратор, создаётся при первом старте; ему же приходят запросы на подтверждение
SUPERVISOR_SYSTEM_EMAIL=
SUPERVISOR_SYSTEM_PASSWORD=              # не короче 12 символов

# SOAP-интеграция портала госзакупок
BASE_URL=https://int.zakupki.gov.ru/eis-integration/services/getDocsIP
DOWNLOAD_URL=https://int.zakupki.gov.ru/dstore/common/download/compound
TOKEN=
SOAP_TIMEOUT=90
DOWNLOAD_TIMEOUT=90

SYSTEM_TOKEN=

# Расписание и повторные попытки
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

`TOKEN` — доступ к SOAP-интеграции портала. `SYSTEM_TOKEN` — обязательная настройка, но собственные эндпоинты сервиса теперь защищены JWT, а не им.

Дополнительно (необязательно): `REGION_PROCESS_CONCURRENCY` (по умолчанию 4), `ARCHIVE_PROCESS_CONCURRENCY` (8), `RECORD_CONCURRENCY` (16) — ограничения параллельности пайплайна.

## Запуск

Перед сборкой положите корневые сертификаты Минцифры в `certs/russian_ca/*.crt` — без них не работает HTTPS к ЕИС, а Dockerfile их копирует. Папка `certs/` в `.gitignore`.

```bash
cp .env.example .env   # и заполните значения
docker compose up --build
```

Приложение — `http://localhost:8002`, PostgreSQL — порт `5434`. Войдите под `SUPERVISOR_SYSTEM_EMAIL` / `SUPERVISOR_SYSTEM_PASSWORD`.

## Перенос данных из старой версии

Скрипты в `tests/` загружают дампы старой версии через новый API (нужен запущенный сервис и учётная запись):

```bash
APP_URL=http://localhost:8002 APP_EMAIL=<email> APP_PASSWORD=<пароль> python tests/upload_purchases.py tests/purchases_dump.json
APP_URL=http://localhost:8002 APP_EMAIL=<email> APP_PASSWORD=<пароль> python tests/upload_newsletters.py tests/all_newsletters_dump.json
```

Повторный запуск безопасен: уже существующие записи пропускаются.

## Локальная разработка фронтенда

```bash
cd app/frontend
npm install
npm run dev
```

Vite (`http://localhost:5173`) проксирует `/users`, `/purchases`, `/newsletters` и `/services` на бэкенд `http://localhost:8002`.

## Лицензия

MIT, см. [LICENSE](LICENSE).
