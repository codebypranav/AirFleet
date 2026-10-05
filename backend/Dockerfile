# backend/Dockerfile

FROM python:3.13-slim

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
RUN chmod +x /app/launcher.sh

EXPOSE 8000

CMD ["/app/launcher.sh"]
