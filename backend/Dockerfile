# Wind Desk API (FastAPI). Used by docker-compose; the root Dockerfile builds the
# single-container image (API + React UI) for Heroku.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# Dependencies first so code changes don't invalidate the pip layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY data ./data

# Run as an unprivileged user; .cache holds the last good live fetch (fallback only).
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/.cache \
    && chown appuser /app/.cache
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=4)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
