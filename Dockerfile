# ---------- frontend build ----------
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY app/frontend/package*.json ./
RUN npm ci
COPY app/frontend ./
RUN npm run build


# ---------- backend runtime ----------
FROM python:3.12-slim

WORKDIR /app

# Установка российских корневых сертификатов Минцифры
# (требуется для HTTPS-взаимодействия с ЕИС на int.zakupki.gov.ru,
#  замена сертификата безопасности RSA на сертификат Минцифры России)
COPY certs/russian_ca/*.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates

RUN set -eux; \
    sed -i 's/^Components: main$/Components: main contrib non-free non-free-firmware/' /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        unrar \
        libreoffice \
        libreoffice-writer \
        fonts-dejavu-core \
        tzdata \
        libglib2.0-0 \
        libgl1 \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-eng; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Добавляем российские корневые сертификаты Минцифры в certifi (т.к. Python requests
# использует certifi, а не системный CA store), чтобы SSL-соединение с ЕИС работало.
RUN cat /etc/ssl/certs/ca-certificates.crt >> /usr/local/lib/python3.12/site-packages/certifi/cacert.pem

COPY app ./app

# Заменяем старую статику результатом сборки React/Vite
RUN rm -rf static
COPY --from=frontend-build /frontend/dist ./static

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]