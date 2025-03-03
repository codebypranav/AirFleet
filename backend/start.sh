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
    echo "DATABASE_URL is NOT SET!"
fi

echo "PORT: ${PORT:-8000}"

# Test direct connection to PostgreSQL
echo "Testing direct PostgreSQL connection..."
python test_db_connection.py

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
python manage.py wait_for_db || { echo "Database connection failed"; exit 1; }

# Run diagnostic script
echo "Running database diagnostics..."
python diagnose_db.py

# Run comprehensive database initialization
echo "Running database initialization script..."
python initialize_db.py || { echo "Database initialization failed"; exit 1; }

# Run diagnostic script again to confirm success
echo "Running post-initialization diagnostics..."
python diagnose_db.py

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Static file collection failed"; exit 1; }

# Start server with the correct WSGI application path
echo "Starting server..."
export PYTHONPATH=/app:$PYTHONPATH
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app --log-level debug