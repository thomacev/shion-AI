#!/bin/sh
set -e

echo "Starting application entrypoint..."

echo "Waiting for PostgreSQL..."

MAX_RETRIES=30
RETRY_COUNT=0

until pg_isready \
    -h db \
    -p 5432 \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB"
do
    RETRY_COUNT=$((RETRY_COUNT + 1))

    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: PostgreSQL is not ready after $MAX_RETRIES attempts."
        exit 1
    fi

    echo "Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

echo "Database is ready."

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI..."
exec uvicorn app.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4