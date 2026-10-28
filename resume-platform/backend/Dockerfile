# FastAPI backend: parsing, matching, rendering and validation.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# poppler-utils: independent pdftotext parse-back check.
# Carlito / Liberation: metric-compatible Calibri / Times fonts embedded in generated PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils fonts-crosextra-carlito fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data \
    && chown -R app:app /data
USER app

ENV RIP_DATA_DIR=/data
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

# Apply migrations, then serve. Bound to all interfaces inside the container only;
# docker-compose publishes the port on 127.0.0.1.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
