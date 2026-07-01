#!/bin/bash
set -e

echo "Starting application entrypoint script..."

echo "Waiting for database to be ready..."

MAX_RETRIES=30
RETRY_COUNT=0
until python -c "
import psycopg2
import sys
import os
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Database not ready after $MAX_RETRIES attempts. Exiting."
        exit 1
    fi
    echo "Attempt $RETRY_COUNT/$MAX_RETRIES - waiting 2 seconds..."
    sleep 2
done

echo "Database is ready."

echo "Checking current migration state..."
if ! alembic upgrade head; then
    echo "ERROR: Migration failed"
    echo "Current state:"
    alembic current
    echo "Migration history:"
    alembic history --verbose
    echo "To recover manually:"
    echo "1. Connect to the database and inspect the state"
    echo "2. Run 'alembic downgrade -1' to rollback the last migration"
    echo "3. Fix the migration file and redeploy"
    exit 1
fi

echo "Migrations completed successfully"
echo "Current migration state:"
alembic current

echo "Starting the application..."
exec uvicorn app.app:app --host 0.0.0.0 --port 8000 --workers 4