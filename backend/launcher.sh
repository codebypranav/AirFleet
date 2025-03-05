#!/bin/bash

echo "=== RUNNING DATABASE SETUP AND MIGRATIONS ==="
python /app/force_migrations.py

echo "=== CLEANING UP TEST DATA ==="
python /app/cleanup_test_data.py

echo "=== COLLECTING STATIC FILES ==="
python /app/manage.py collectstatic --noinput

echo "=== STARTING SERVER ==="
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app --log-level debug 