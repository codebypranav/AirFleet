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
gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:$PORT