# AirFleet

AirFleet is an AI-enabled pilot logbook and operations dashboard designed for both real-world aviation workflows and sim-flying use cases. It is meant as a learning project and experimentation platform rather than an official flight logging system.

## Overview

The project combines:
- a Django REST API backend
- a Next.js frontend
- PostgreSQL persistence
- JWT-based auth
- AI-assisted air operations workflows
- flight and user management features

## Tech stack

- Backend: Python, Django, Django REST Framework
- Frontend: Next.js, React, TypeScript
- Database: PostgreSQL
- Containerization: Docker Compose
- AI: OpenAI integration via Python client

## Project structure

```text
backend/
  AirFleet_api/
  flights/
  users/
  manage.py
  requirements.txt
frontend/
  app/
  components/
  lib/
docker-compose.yml
```

## Local development

Prerequisites:
- Docker
- Docker Compose

From the project root:

```bash
docker compose up --build
```

This will start:
- PostgreSQL on port 5432
- Django backend on port 8000
- Next.js frontend on port 3000

## Access the app

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Admin: http://localhost:8000/admin

## Backend setup

If you want to run the backend directly:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

## Notes

This project is intended for experimentation and personal development. It is not certified or suitable for official operational use without further validation, compliance review, and safety controls.
