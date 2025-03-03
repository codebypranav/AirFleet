#!/bin/bash

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
python manage.py wait_for_db

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Start server
echo "Starting server..."
gunicorn airfleet.wsgi:application --bind 0.0.0.0:8000