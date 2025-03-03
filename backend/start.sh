#!/bin/bash

# Print environment variables for debugging
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "ALLOWED_HOSTS: $ALLOWED_HOSTS"
echo "DEBUG: $DEBUG"
echo "DATABASE_URL: ${DATABASE_URL:-Not Set}"
echo "PORT: ${PORT:-8000}"

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
python manage.py wait_for_db || { echo "Database connection failed"; exit 1; }

# Run diagnostic script
echo "Running database diagnostics..."
python diagnose_db.py

# Show current migration status
echo "Current migration status:"
python manage.py showmigrations

# Make migrations (in case they haven't been created yet)
echo "Creating migrations if needed..."
python manage.py makemigrations users --verbosity 2

# Run migrate with verbosity to see exactly what's happening
echo "Running migrations with verbosity..."
python manage.py migrate --noinput --verbosity 2 || { echo "Migrations failed"; exit 1; }

# Explicitly migrate the users app
echo "Explicitly migrating users app..."
python manage.py migrate users --noinput --verbosity 2 || { echo "Users migrations failed"; exit 1; }

# Verify users_customuser table was created
echo "Verifying users_customuser table exists..."
python -c "
import os, django, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirFleet_api.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute(\"\"\"
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'users_customuser'
        );
    \"\"\")
    result = cursor.fetchone()[0]
    if not result:
        print('ERROR: users_customuser table does not exist!')
        sys.exit(1)
    else:
        print('SUCCESS: users_customuser table exists')
" || { echo "Table verification failed"; exit 1; }

# Run diagnostic script again to confirm migrations worked
echo "Running post-migration diagnostics..."
python diagnose_db.py

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Static file collection failed"; exit 1; }

# Start server with the correct WSGI application path
echo "Starting server..."
export PYTHONPATH=/app:$PYTHONPATH
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app --log-level debug