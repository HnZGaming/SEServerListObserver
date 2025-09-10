#!/bin/sh
set -e

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
