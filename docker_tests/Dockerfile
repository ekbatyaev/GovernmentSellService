FROM python:3.12-slim

WORKDIR /app

RUN set -eux; \
    sed -i 's/^Components: main$/Components: main contrib non-free non-free-firmware/' /etc/apt/sources.list.d/debian.sources; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        unrar \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        fonts-dejavu-core \
        tzdata; \
    rm -rf /var/lib/apt/lists/*

COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY .. /app

ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Moscow

CMD ["python", "-m", "app.goszakupki_requests.document_consistent"]