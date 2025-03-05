#!/bin/bash

# This script is used to start the Django application

set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting AirFleet API service..."

# Function to clean proxy environment variables
clean_proxies() {
    echo "Cleaning proxy environment variables..."
    unset HTTP_PROXY
    unset HTTPS_PROXY
    unset http_proxy
    unset https_proxy
    unset ALL_PROXY
    unset all_proxy
    unset NO_PROXY
    unset no_proxy
}

# Clean proxy variables
clean_proxies

# Run diagnostic script if it exists
if [ -f "diagnose_railway.py" ]; then
    echo "Running Railway diagnostics..."
    python diagnose_railway.py || echo "Diagnostics failed but continuing with startup"
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set!"
    echo "Please set the DATABASE_URL environment variable to connect to your PostgreSQL database."
    exit 1
fi

# Check if OpenAI API key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "WARNING: OPENAI_API_KEY environment variable is not set!"
    echo "The application will not be able to use OpenAI features."
else
    echo "OpenAI API key is set. Length: ${#OPENAI_API_KEY} chars"
fi

# Apply migrations
echo "Applying database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn AirFleet_api.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 2 --worker-tmp-dir /dev/shm