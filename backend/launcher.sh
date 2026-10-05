#!/bin/bash
set -e

echo "=== APPLYING DATABASE MIGRATIONS ==="
python /app/manage.py migrate --noinput

echo "=== COLLECTING STATIC FILES ==="
python /app/manage.py collectstatic --noinput

echo "=== STARTING SERVER ==="
exec gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app
