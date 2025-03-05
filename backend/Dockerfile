# backend/Dockerfile

FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV DJANGO_SETTINGS_MODULE=AirFleet_api.settings
ENV PYTHONPATH=/app:$PYTHONPATH

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
    chmod +x /app/force_migrations.py && \
    chmod +x /app/cleanup_test_data.py && \
    chmod +x /app/launcher.sh

EXPOSE 8000

# Use the launcher script directly - Railway can't skip this
CMD ["/app/launcher.sh"]
