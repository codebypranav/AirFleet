#!/bin/bash

# Print environment variables for debugging
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "ALLOWED_HOSTS: $ALLOWED_HOSTS"
echo "DEBUG: $DEBUG"

# Display database connection info (masking sensitive parts)
if [ -n "$DATABASE_URL" ]; then
    # Display the DATABASE_URL with password masked
    MASKED_URL=$(echo $DATABASE_URL | sed -E 's/\/\/([^:]+):([^@]+)@/\/\/\1:******@/')
    echo "DATABASE_URL is set: $MASKED_URL"
else
    echo "WARNING: DATABASE_URL is NOT SET!"
    echo "Please set DATABASE_URL to \${{ Postgres.DATABASE_URL }} in Railway dashboard"
fi

echo "PORT: ${PORT:-8000}"

# Test direct connection to PostgreSQL
echo "Testing direct PostgreSQL connection..."
python test_db_connection.py

# Force run migrations to ensure database tables are created
echo "Force running migrations..."
python force_migrations.py

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Static file collection failed"; exit 1; }

# Start server with the correct WSGI application path
echo "Starting server..."
export PYTHONPATH=/app:$PYTHONPATH
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app --log-level debug