#!/bin/sh
set -e

# Wait for Postgres to be ready
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
  echo "Waiting for postgres..."
  sleep 2
done

# Convert schema file to Unix line endings (no-op if already correct)
dos2unix /app/postgres_schema.sql || true

# Run schema migration with fail-fast on error, using PGPASSWORD for non-interactive auth
PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /app/postgres_schema.sql

echo "Postgres schema migration complete."
echo "MODE: $MODE"

# dev mode
if [ "$MODE" != "prod" ] && [ -n "$MODE" ]; then
    echo "Running in development mode: executing main.py directly."
    exec python /app/main.py
    exit 0
fi

# prod mode
# Regenerate env.sh with current environment (including Docker secrets/compose envs)
printenv | sed 's/^/export /' > /env.sh
echo "Running in production mode: starting cron for scheduled execution."
cron &
tail -F /var/log/cron.log
