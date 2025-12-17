#!/bin/bash

set -e  # Exit on error
echo "Debug mode: $DEBUG"
echo "Environment: $ENVIRONMENT"

# Set default ports if not specified
DEBUG_PORT=${DEBUG_PORT:-5678}
HTTP_PORT=${HTTP_PORT:-8000}
echo "Debug port: $DEBUG_PORT"
echo "HTTP port: $HTTP_PORT"

# Wait for database to be ready before proceeding
# This prevents race conditions when database is starting up alongside the app
echo "Waiting for database to be ready..."
MAX_RETRIES=${DB_WAIT_RETRIES:-60}
RETRY_INTERVAL=${DB_WAIT_INTERVAL:-5}
for i in $(seq 1 $MAX_RETRIES); do
    if python -c "
import asyncio
import sqlalchemy as sa
from cognee.infrastructure.databases.relational import get_relational_engine

async def check_db():
    engine = get_relational_engine()
    try:
        async with engine.engine.connect() as conn:
            await conn.execute(sa.text('SELECT 1'))
        return True
    except Exception as e:
        print(f'Database check failed: {e}')
        return False

exit(0 if asyncio.run(check_db()) else 1)
" 2>/dev/null; then
        echo "Database is ready!"
        break
    fi
    echo "Attempt $i/$MAX_RETRIES: Database not ready, waiting ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
    if [ $i -eq $MAX_RETRIES ]; then
        echo "ERROR: Database failed to become ready after $MAX_RETRIES attempts"
        exit 1
    fi
done

# CRITICAL: Create base tables via SQLAlchemy BEFORE running Alembic migrations
# This fixes the chicken-and-egg problem where migrations expect tables to exist
# but tables are normally only created by SQLAlchemy after migrations complete.
# By running create_db_and_tables() first, we ensure all model tables exist
# with the current schema, and Alembic migrations can then safely modify them.
echo "Creating base database tables via SQLAlchemy..."
python -c "
import asyncio
from cognee.infrastructure.databases.relational import create_db_and_tables

async def init_tables():
    await create_db_and_tables()
    print('Base tables created successfully')

asyncio.run(init_tables())
"

# Run Alembic migrations with proper error handling.
# Note on UserAlreadyExists error handling:
# During database migrations, we attempt to create a default user. If this user
# already exists (e.g., from a previous deployment or migration), it's not a
# critical error and shouldn't prevent the application from starting. This is
# different from other migration errors which could indicate database schema
# inconsistencies and should cause the startup to fail. This check allows for
# smooth redeployments and container restarts while maintaining data integrity.
echo "Running database migrations..."

MIGRATION_OUTPUT=$(alembic upgrade head 2>&1) || MIGRATION_EXIT_CODE=$?
MIGRATION_EXIT_CODE=${MIGRATION_EXIT_CODE:-0}

if [[ $MIGRATION_EXIT_CODE -ne 0 ]]; then
    if [[ "$MIGRATION_OUTPUT" == *"UserAlreadyExists"* ]] || [[ "$MIGRATION_OUTPUT" == *"User default_user@example.com already exists"* ]]; then
        echo "Warning: Default user already exists, continuing startup..."
    else
        echo "Migration output: $MIGRATION_OUTPUT"
        echo "Migration failed with unexpected error."
        exit 1
    fi
fi

echo "Database migrations done."

echo "Starting server..."

# Add startup delay to ensure DB is ready
sleep 2

# Modified Gunicorn startup with error handling
if [ "$ENVIRONMENT" = "dev" ] || [ "$ENVIRONMENT" = "local" ]; then
    if [ "$DEBUG" = "true" ]; then
        echo "Waiting for the debugger to attach..."
        # DEBUG_HOST defaults to localhost for security; set to 0.0.0.0 only if remote debugging is needed
        DEBUG_HOST=${DEBUG_HOST:-127.0.0.1}
        exec debugpy --wait-for-client --listen $DEBUG_HOST:$DEBUG_PORT -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker -t 30000 --bind=0.0.0.0:$HTTP_PORT --log-level debug --reload --access-logfile - --error-logfile - cognee.api.client:app
    else
        exec gunicorn -w 1 -k uvicorn.workers.UvicornWorker -t 30000 --bind=0.0.0.0:$HTTP_PORT --log-level debug --reload --access-logfile - --error-logfile - cognee.api.client:app
    fi
else
    exec gunicorn -w 1 -k uvicorn.workers.UvicornWorker -t 30000 --bind=0.0.0.0:$HTTP_PORT --log-level error --access-logfile - --error-logfile - cognee.api.client:app
fi
