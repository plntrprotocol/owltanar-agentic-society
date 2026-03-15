# syntax=docker/dockerfile:1

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    redis-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Add additional production dependencies
RUN pip install --no-cache-dir \
    gunicorn \
    celery[redis] \
    redis \
    psycopg2-binary \
    asyncpg \
    python-multipart \
    httpx

# Copy application code
COPY *.py ./
COPY data ./data
COPY commons-*.py ./
COPY commons-*.json ./
COPY *.json ./
COPY *.md ./

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose ports
EXPOSE 8000 5555

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run gunicorn for production, celery worker in background
CMD gunicorn platform_server:app --host 0.0.0.0 --port 8000 --workers 4 --timeout 120 &
celery -A celery_worker worker --loglevel=info --detach
wait
