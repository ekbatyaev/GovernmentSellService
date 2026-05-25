FROM python:3.12-slim

WORKDIR /app

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

COPY app .

CMD ["uvicorn", "database.main:app", "--host", "0.0.0.0", "--port", "8000"]