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

# Run migrations
echo "Running migrations..."
python manage.py migrate || { echo "Migrations failed"; exit 1; }

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || { echo "Static file collection failed"; exit 1; }

# Start server with the correct WSGI application path
echo "Starting server..."
export PYTHONPATH=/app:$PYTHONPATH
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --chdir /app --log-level debug
```
```bash
#!/bin/bash

# Print environment variables for debugging (excluding sensitive ones)
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "ALLOWED_HOSTS: $ALLOWED_HOSTS"
echo "DEBUG: $DEBUG"

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start the server
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:$PORT
```
```bash
#!/bin/bash

# Print environment variables for debugging
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "ALLOWED_HOSTS: $ALLOWED_HOSTS"
echo "DEBUG: $DEBUG"

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
python manage.py wait_for_db

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start server with the correct WSGI application path
echo "Starting server..."
export PYTHONPATH=/app:$PYTHONPATH
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:$PORT --chdir /app