FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

RUN pip install --upgrade pip && \
    pip install \
        "alembic>=1.18.5" \
        "asyncpg>=0.31.0" \
        "celery[redis]>=5.6.3" \
        "fastapi>=0.138.1" \
        "flower>=2.0.1" \
        "httpx>=0.28.1" \
        "locust>=2.44.4" \
        "openai>=2.44.0" \
        "passlib[bcrypt]>=1.7.4" \
        "prometheus-fastapi-instrumentator>=8.0.2" \
        "pwdlib[argon2]>=0.3.0" \
        "pydantic[email]>=2.13.4" \
        "pydantic-settings>=2.14.2" \
        "redis>=6.4.0" \
        "sqlalchemy>=2.0.51" \
        "uvicorn>=0.49.0" \
        "python-dotenv>=1.2.2" \
        "python-jose[cryptography]>=3.5.0" \
        "python-multipart>=0.0.32" \
        "requests>=2.34.2" \
        "slowapi>=0.1.10" \
        "structlog>=26.1.0"

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini main.py ./
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh
RUN chmod +x ./scripts/entrypoint.sh

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["./scripts/entrypoint.sh"]