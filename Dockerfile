FROM python:3.13.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_MODE=production \
    ENV=production \
    COOKIE_SECURE=true \
    VIRUS_SCAN_STRICT=true \
    VIGZONE_DATA_DIR=/app/data \
    WORKERS=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    clamav \
    clamav-freshclam \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-sin \
    tesseract-ocr-tam \
    && freshclam --quiet \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN groupadd --gid 10001 vigzone \
    && useradd --uid 10001 --gid vigzone --create-home --shell /usr/sbin/nologin vigzone

COPY --chown=vigzone:vigzone . .
RUN mkdir -p /app/data && chown -R vigzone:vigzone /app/data

USER vigzone

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8000') + '/health/live', timeout=5)" || exit 1

CMD ["python", "start.py"]
