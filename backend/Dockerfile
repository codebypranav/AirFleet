# backend/Dockerfile

FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . /app/

# Make sure the scripts are executable
RUN chmod +x /app/start.sh && \
    chmod +x /app/diagnose_db.py

# Set Python path for the application
ENV PYTHONPATH=/app:$PYTHONPATH

EXPOSE 8000

# Use the start script
CMD ["/app/start.sh"]
