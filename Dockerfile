FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Default to testing so platform deployments that forget envs don't block startup.
    APP_MODE=testing \
    ENV=development \
    COOKIE_SECURE=true \
    VIRUS_SCAN_STRICT=false \
    VIGZONE_DATA_DIR=/app/data \
    WORKERS=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libmagic1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-sin \
    tesseract-ocr-tam \
    && rm -rf /var/lib/apt/lists/*

# Note: We avoid installing clamav and running freshclam during image build because
# freshclam often fails in hosted build environments. If you need ClamAV at runtime,
# install it and run freshclam on container start, or mount a volume with signatures.

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
