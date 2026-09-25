# AirFleet

AirFleet is a personal aviation operations and flight logging project that combines a Django backend, a Next.js frontend, and AI-assisted narrative generation. The application is designed to help pilots or sim pilots store flight entries, manage user accounts, and generate short, human-readable summaries from raw flight data.

## Product goal

The system is meant to function as a lightweight aviation workspace with:

- flight record storage
- user-specific flight history
- JWT-based authentication
- AI-generated narratives summarizing flight events
- a dashboard and UI for reviewing flight data

This is a learning-oriented application rather than a certified aviation compliance system, and it should not be treated as an official flight-logging platform without additional validation.

## Technical architecture

### Backend
- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT authentication via `djangorestframework-simplejwt`
- OpenAI API integration for narrative generation

The backend is organized around Django apps:

- `backend/AirFleet_api/` — project configuration and settings
- `backend/flights/` — flight models, serializers, and API logic
- `backend/users/` — user auth and profile logic

### Frontend
- Next.js
- React
- TypeScript
- App Router architecture
- API consumption for login, flight CRUD, and AI generation

### Database and infrastructure
- PostgreSQL is used as the primary persistence layer
- Docker Compose orchestrates the stack for local development
- CORS is enabled for the Next.js frontend on `localhost:3000`

## Core implementation details

### Authentication and authorization
The backend uses Django REST Framework with JWT authentication. This means the client obtains access and refresh tokens, then includes the access token on authenticated requests.

The auth configuration is defined in `backend/AirFleet_api/settings.py`, which sets:

- `AUTH_USER_MODEL = 'users.CustomUser'`
- JWT token lifetime and refresh rotation
- REST framework authentication classes
- CORS headers for local frontend origin access

### Flight API layer
The `flights` app contains the main API views:

- `FlightListView` handles listing and creating flight records
- `FlightDetailView` handles get/update/delete for a single flight
- `generate_narrative` calls the OpenAI API and returns a generated narrative for a flight

This is the main business logic for recording aviation events and summarizing them for the user.

### AI narrative generation
The AI flow is particularly important. In `backend/flights/views.py`, the app tries multiple OpenAI client strategies in order to generate a narrative based on structured flight metadata such as:

- departure airport and time
- arrival airport and time
- total flight time
- distance
- aircraft registration
- aircraft condition
- weather conditions

The generated response is then returned to the frontend as a natural-language summary.

## Repository structure

```text
backend/
  AirFleet_api/
  flights/
  users/
  manage.py
  requirements.txt
  start.sh
  initialize_db.py
  force_migrations.py
frontend/
  app/
  components/
  lib/
docker-compose.yml
```

## Local development

### Option 1: Docker Compose
From the project root:

```bash
docker compose up --build
```

This starts:

- PostgreSQL
- Django backend on port `8000`
- Next.js frontend on port `3000`

### Option 2: Manual backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Option 3: Frontend setup

```bash
cd frontend
npm install
npm run dev
```

## Environment variables

The application relies on values such as:

```bash
SECRET_KEY=your-secret
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/airfleet
OPENAI_API_KEY=your-openai-key
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000
```

## Usage flow

Typical usage looks like this:

1. user signs in or registers
2. flight entries are saved through the Django REST API
3. the frontend displays the user’s flight history
4. the AI endpoint converts flight metadata into a narrative summary
5. the user can review and edit flights over time

## Why this project matters technically

AirFleet brings together multiple engineering concerns:

- API design and authentication
- relational database modeling
- frontend-backend integration
- secure env configuration
- AI API integration in real-world app code


## Notes

- The application includes several debugging and migration helper scripts because the project was iterated through local setup and deployment issues.
- The project is intended as a personal engineering exercise and should be hardened before any real-world operational deployment.
