FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Every Python module app.py (directly or indirectly) imports at startup —
# missing any of these causes an ImportError and the container crashes
# before it can bind to a port, which shows up on Railway as
# "Application failed to respond".
COPY app.py .
COPY vigzone_ai.py .
COPY auth.py .
COPY file_processing.py .
COPY self_learning.py .
COPY image_generation.py .
COPY web_search.py .
COPY stream_manager.py .
COPY virus_scanner.py .
COPY start.py .
# Optional modules — imported inside try/except in vigzone_ai.py. They do
# exist in this project, so copy them directly (if you ever delete them,
# switch these two lines to a wildcard COPY or remove them).
COPY realworld_data.py .
COPY website_builder.py .
COPY static/ static/

ENV PYTHONUNBUFFERED=1 \
    ENV=production

# NOTE: no hardcoded PORT here — Railway (and most hosts) inject their own
# PORT value at runtime, and the app must listen on THAT port, not a fixed
# one, or the platform's proxy can never reach it.

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8000') + '/health')" || exit 1

EXPOSE 8000

# start.py reads PORT itself in Python — no reliance on the host actually
# running this command through a shell that expands $PORT (some platforms'
# "custom start command" features run commands without a shell, which left
# a literal "$PORT" string being passed to uvicorn instead of a number).
CMD ["python", "start.py"]

