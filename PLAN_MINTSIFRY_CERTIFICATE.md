# План: Интеграция сертификата Минцифры России для HTTPS-взаимодействия с ЕИС

## 1. Проблема

Ошибка `SSL: CERTIFICATE_VERIFY_FAILED` при соединении с `int.zakupki.gov.ru`:

```
SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] 
certificate verify failed: self-signed certificate in certificate chain'))
```

Причина: ЕИС (единая информационная система в сфере закупок) сменила сертификат RSA на сертификат Минцифры России. Встроенный в Debian/Python набор корневых сертификатов (CA bundle) не содержит российские корневые сертификаты, поэтому SSL-рукопожатие отклоняется.

Уведомление: "до 04.07.2026 необходимо установить сертификат Минцифры России в используемом программном обеспечении".

## 2. Текущая архитектура

### Стек HTTPS-соединения

```
requests (Python) → urllib3 → ssl (openssl)
         ↓
использует системный CA bundle
  (/etc/ssl/certs/ca-certificates.crt из пакета ca-certificates)
         ↓
в Debian slim (базовый образ python:3.12-slim)
  НЕ содержит российские корневые сертификаты
```

### Файлы, выполняющие HTTPS-запросы к `int.zakupki.gov.ru`

| Файл | Функция | Роль |
|------|---------|------|
| [`app/goszakupki_requests/xml_archives_request.py`](app/goszakupki_requests/xml_archives_request.py:33) | [`build_session()`](app/goszakupki_requests/xml_archives_request.py:33) | Создаёт глобальный `requests.Session` для SOAP-запросов |
| [`app/goszakupki_requests/xml_archives_request.py`](app/goszakupki_requests/xml_archives_request.py:98) | [`soap_post()`](app/goszakupki_requests/xml_archives_request.py:98) | POST-запрос к `BASE_URL` (int.zakupki.gov.ru) |
| [`app/goszakupki_requests/get_documents_consistent.py`](app/goszakupki_requests/get_documents_consistent.py:193) | [`make_session()`](app/goszakupki_requests/get_documents_consistent.py:193) | Создаёт сессию для скачивания архивов |

### Имеющиеся сертификаты

В [`certs/`](certs/) лежат сертификаты для собственного домена (`tenders.systeme.ru`) — они НЕ относятся к задаче.

## 3. Решение (референс: max-technical-helper)

В проекте [`max-technical-helper/Dockerfile`](http://github.com/AlexBessarabenko/max-technical-helper) (строка 4-5) используется стандартный механизм Debian:

```dockerfile
COPY certs/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

Команда [`update-ca-certificates`](https://manpages.debian.org/bookworm/ca-certificates/update-ca-certificates.8.html) пересобирает файл `/etc/ssl/certs/ca-certificates.crt`, добавляя в него PEM-сертификаты из `/usr/local/share/ca-certificates/`. После этого все программы, использующие OpenSSL (включая Python/requests/urllib3), автоматически доверяют этим сертификатам.

## 4. Требуемые изменения

### 4.1. Добавить российские сертификаты в репозиторий

**Источник:** `/home/aiuser/` — zip-архивы, распакованные в `/tmp/cert_examine/`

| Файл | Формат | Назначение |
|------|--------|------------|
| `russian_trusted_root_ca_pem.crt` | PEM ✅ | Корневой RSA (2022) |
| `russian_trusted_root_ca_gost_2025_pem.crt` | DER (бинарный) ❌ | Корневой ГОСТ (2025) — **нужна конвертация в PEM** |
| `russian_trusted_sub_ca_pem.crt` | PEM ✅ | Промежуточный RSA (2022) |
| `russian_trusted_sub_ca_2024_pem.crt` | PEM ✅ | Промежуточный RSA (2024) |
| `russian_trusted_sub_ca_gost_2025_pem.crt` | DER (бинарный) ❌ | Промежуточный ГОСТ (2025) — **нужна конвертация в PEM** |

Требование `update-ca-certificates`: все файлы должны иметь расширение `.crt` и содержать PEM (base64). DER-формат не поддерживается.

**Действие:** создать директорию [`certs/russian_ca/`](certs/russian_ca/) и разместить в ней все 5 сертификатов в PEM-формате.

### 4.2. Конвертировать DER → PEM для ГОСТ-сертификатов

Использовать OpenSSL:

```bash
# Корневой ГОСТ 2025
openssl x509 -in certs/russian_ca/russian_trusted_root_ca_gost_2025_pem.crt \
  -inform DER -outform PEM \
  -out certs/russian_ca/russian_trusted_root_ca_gost_2025_pem.crt

# Промежуточный ГОСТ 2025  
openssl x509 -in certs/russian_ca/russian_trusted_sub_ca_gost_2025_pem.crt \
  -inform DER -outform PEM \
  -out certs/russian_ca/russian_trusted_sub_ca_gost_2025_pem.crt
```

**Итог:** после конвертации оба файла будут содержать валидный PEM с маркерами `-----BEGIN CERTIFICATE-----` / `-----END CERTIFICATE-----`.

### 4.3. Изменить [`Dockerfile`](Dockerfile)

Добавить блок после установки системных пакетов (до `COPY requirements.txt`):

```dockerfile
# Установка российских корневых сертификатов Минцифры
# (требуется для HTTPS-взаимодействия с ЕИС на int.zakupki.gov.ru)
COPY certs/russian_ca/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
```

> **Почему после установки пакетов?** Пакет `ca-certificates` уже присутствует в `python:3.12-slim`. Команда `update-ca-certificates` лишь дополняет его российскими сертификатами. Если ca-certificates не установлен — нужно добавить `apt-get install -y ca-certificates`.

### 4.4. Проверить совместимость с `REQUESTS_CA_BUNDLE` (опционально)

Если Python-окружение использует отдельный CA bundle (например, через переменную окружения `REQUESTS_CA_BUNDLE` или `SSL_CERT_FILE`), может потребоваться скопировать сертификаты и туда.

По умолчанию `requests` использует сертификаты из `certifi`, который в Debian-системах линкуется к `/etc/ssl/certs/ca-certificates.crt`. `update-ca-certificates` обновляет как раз этот файл, поэтому дополнительных действий не требуется.

## 5. Схема изменений

```
До:
  Dockerfile → python:3.12-slim + apt пакеты + pip install
               → requests.session → ssl → системный CA store (без российских сертификатов)
               → SSLHandshakeError ❌

После:
  Dockerfile → python:3.12-slim + apt пакеты 
               + COPY certs/russian_ca/*.crt + update-ca-certificates
               → системный CA store (с российскими сертификатами)
               → requests.session → ssl → обновлённый CA store
               → успешное соединение ✅
```

## 6. Состав изменений (checklist)

- [ ] Создать [`certs/russian_ca/`](certs/russian_ca/)
- [ ] Скопировать `russian_trusted_root_ca_pem.crt` (PEM — без изменений)
- [ ] Скопировать `russian_trusted_sub_ca_pem.crt` (PEM — без изменений)
- [ ] Скопировать `russian_trusted_sub_ca_2024_pem.crt` (PEM — без изменений)
- [ ] Конвертировать `russian_trusted_root_ca_gost_2025_pem.crt` DER→PEM
- [ ] Конвертировать `russian_trusted_sub_ca_gost_2025_pem.crt` DER→PEM
- [ ] Изменить [`Dockerfile`](Dockerfile): добавить `COPY` + `RUN update-ca-certificates`
- [ ] Пересобрать образ: `docker compose build`
- [ ] Проверить: запустить контейнер и выполнить тестовый запрос к `int.zakupki.gov.ru`

## 7. Верификация

После применения изменений проверить:

1. Внутри контейнера:
```bash
docker compose run --rm app python -c "
import requests
r = requests.post('https://int.zakupki.gov.ru/eis-integration/services/getDocsIP')
print(r.status_code)
"
```
   — ожидается HTTP-ответ (501/400/200 — любой, но не SSLError).

2. Либо проверить корневой сертификат:
```bash
docker compose run --rm app openssl s_client \
  -connect int.zakupki.gov.ru:443 -showcerts
```

3. Тестовая страница из уведомления (если доступно):
```
https://rus-ssl.zakupki.gov.ru
```

## 8. Риски

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Сертификаты ЕИС отозваны или заменены | Низкая | Обновить сертификаты из zip-архивов Минцифры |
| GOST-сертификаты не подходят для RSA-соединения | Средняя | ЕИС может использовать RSA-сертификаты (russian_trusted_root_ca_pem.crt + sub_ca). GOST — для совместимости |
| Контейнер не имеет доступа к сети ЕИС | Низкая | Проверить DNS и сетевые политики |
| `update-ca-certificates` не найден | Низкая | В `python:3.12-slim` есть пакет `ca-certificates` |