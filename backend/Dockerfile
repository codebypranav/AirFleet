# backend/Dockerfile

FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DJANGO_SETTINGS_MODULE=AirFleet_api.settings

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy all files
COPY . /app/

# Make scripts executable
RUN chmod +x /app/start.sh && \
    chmod +x /app/diagnose_db.py && \
    chmod +x /app/initialize_db.py && \
    chmod +x /app/test_db_connection.py && \
    chmod +x /app/force_migrations.py

# Set Python path for the application
ENV PYTHONPATH=/app:$PYTHONPATH

# Create a pre-start script to run migrations
RUN echo '#!/bin/bash\n\
echo "Running forced migrations..."\n\
python /app/force_migrations.py\n\
echo "Starting application..."\n\
exec "$@"' > /app/entrypoint.sh && \
chmod +x /app/entrypoint.sh

EXPOSE 8000

# Use the entrypoint script and start.sh
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/start.sh"]
