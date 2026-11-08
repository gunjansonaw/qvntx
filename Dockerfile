# Single-container production image: FastAPI serves both /api and the built React UI.
# Used by Heroku (heroku.yml) and any container host. Heroku injects $PORT.
#   docker build -t wind-desk . && docker run -p 8000:8000 wind-desk

# --- 1. build the React app --------------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2. Python runtime -------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000 \
    STATIC_DIR=/app/static

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/data ./data
COPY --from=frontend /frontend/dist ./static

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/.cache \
    && chown appuser /app/.cache
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=4)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
