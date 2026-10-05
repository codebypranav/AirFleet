# AirFleet

AirFleet is a personal aviation operations and flight logging project that combines a Django backend, a Next.js frontend, and AI-assisted narrative generation. The application is designed to help pilots or sim pilots store flight entries, manage user accounts, and generate short, human-readable summaries from raw flight data.

## Product goal

The system is meant to function as a lightweight aviation workspace with:

- flight record storage
- user-specific flight history
- JWT-based authentication
- AI-generated narratives summarizing flight events
- a dashboard and UI for reviewing flight data

## Features

- **Logbook:** add, view, edit and delete flights, with standard columns (PIC, SIC, dual
  received, night, actual and simulated instrument time, day/night landings, approaches,
  cross-country, simulator). Paginated and filterable by date, airport, aircraft and text.
- **Airport data:** a bundled OurAirports extract (public domain) validates ICAO codes,
  suggests airports as you type, and works out great-circle distance. Block time comes from
  the departure and arrival times.
- **Fleet:** an aircraft record per registration with type, class, hours, an inspection
  counter and annual due date. A flight that reports the aircraft *Grounded* blocks new
  flights in it until maintenance is logged.
- **Stats:** totals, hours per month, most-flown routes and aircraft, a great-circle route
  map (Leaflet), passenger/night/IFR currency, and achievements.
- **Stories:** AI narratives are written on request and saved on the flight. The prompt
  includes airport names, weather, night/instrument time and the pilot's notes.
- **Weather and SimBrief:** fetch the departure METAR (aviationweather.gov, last ~15 days)
  or prefill a flight from your latest SimBrief flight plan.
- **Import/export:** CSV export of the logbook (or a filtered slice), and import of AirFleet
  CSVs or ForeFlight logbook exports. Duplicates are skipped and bad rows reported.
- **Accounts:** profile editing, password change, password reset by email, optional Google
  sign-in, and opt-in public pilot profiles and shareable flight pages.
- **Rankings:** by flights, time, distance, longest flight and airports visited, for all
  time, this year or this month.
- **Privacy:** a `/privacy` notice of what is stored and which services see it, and account
  deletion from the profile page that erases the pilot's flights, aircraft and photos.

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
`POST /api/generate-narrative/` takes a `flight_id`, builds a prompt from the stored flight and saves the
result on it (`narrative`, `narrative_generated_at`). It is rate limited per user (`NARRATIVE_RATE`,
default `30/hour`). The prompt includes structured flight metadata such as:

- departure airport and time
- arrival airport and time
- total flight time
- distance
- aircraft registration
- aircraft condition
- weather conditions, night and instrument time, and the pilot's notes

The generated response is returned to the frontend and kept with the flight.

## Repository structure

```text
backend/
  AirFleet_api/
  flights/
  users/
  flights/data/airports.csv.gz
  manage.py
  launcher.sh        # container entrypoint: migrate, collectstatic, gunicorn
  requirements.txt
frontend/
  e2e/               # Playwright end-to-end tests
  src/app/           # pages (App Router)
  src/components/
  src/utils/         # API client and formatting helpers
docker-compose.yml
render.yaml
neon.ts
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

Requires Python 3.12+ (Django 6).

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
python manage.py test  # run the API test suite
```

`flights/data/airports.csv.gz` is generated from
[OurAirports](https://davidmegginson.github.io/ourairports-data/airports.csv): every open
airport and seaplane base with a 4-character ICAO-style code.

### Option 3: Frontend setup

Requires Node.js 20.9+ (Next.js 16).

```bash
cd frontend
npm install
npm run dev
```

Checks: `npm run lint`, `npm run typecheck`, `npm run build`.

### End-to-end tests

Playwright drives the production build against the real API. With Postgres running and
`DATABASE_URL`/`SECRET_KEY` set:

```bash
cd frontend
npx playwright install chromium
npm run build
PYTHON=../backend/.venv/bin/python npm run test:e2e  # starts Django and Next itself
```

CI runs the backend suite (`.github/workflows/backend.yml`) and lint, typecheck, build and
the end-to-end tests (`.github/workflows/frontend.yml`).

## Environment variables

The application relies on values such as:

```bash
SECRET_KEY=your-secret
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/airfleet
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o-mini  # optional, model used for flight narratives
NEXTAUTH_SECRET=your-nextauth-secret
NEXTAUTH_URL=http://localhost:3000
```

Optional:

```bash
# Backend
FRONTEND_URL=https://airfleet.vercel.app  # where password-reset links point
EMAIL_HOST=smtp.example.com               # without it, reset emails are printed to the log
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
DEFAULT_FROM_EMAIL="AirFleet <no-reply@example.com>"
GOOGLE_CLIENT_ID=...                      # enables Google sign-in (same ID as the frontend)
NARRATIVE_RATE=30/hour                    # AI narrative limit per user

# Frontend
GOOGLE_CLIENT_ID=...                      # with GOOGLE_CLIENT_SECRET, shows "Continue with Google"
GOOGLE_CLIENT_SECRET=...
API_URL=...                               # API origin for server-side calls, if it differs from NEXT_PUBLIC_API_URL
NEXT_PUBLIC_ENABLE_DEBUG=true             # turns on the /debug connection page
NEXT_PUBLIC_PRIVACY_CONTACT=you@example.com  # shown on /privacy for data requests
```

For Google sign-in, create an OAuth client (Web application) in Google Cloud and add
`<frontend URL>/api/auth/callback/google` as an authorized redirect URI.

## Deployment

The demo runs entirely on free tiers: Neon (Postgres), Render (Django API) and Vercel (Next.js).

1. **Database (Neon):** create a project at neon.com and copy its connection string
   (it ends in `?sslmode=require`).
2. **Backend (Render):** New → Blueprint → select this repo. Render reads `render.yaml`
   and asks for `DATABASE_URL` (the Neon string) and `OPENAI_API_KEY`; `SECRET_KEY` is generated.
   Migrations run automatically on every start. The free instance sleeps after 15 minutes
   idle, so the first request after a pause takes about a minute.
3. **Frontend (Vercel):** import the repo with root directory `frontend` and Node 22, and set
   `NEXT_PUBLIC_API_URL` to the Render URL (e.g. `https://airfleet-api.onrender.com`),
   plus `NEXTAUTH_SECRET` and `NEXTAUTH_URL`. The backend accepts requests from
   `airfleet.vercel.app`, `airfleet-project.vercel.app` and their preview URLs; add other
   domains to `CORS_ALLOWED_ORIGINS` in `backend/AirFleet_api/settings.py`.

To reset the demo data, use Neon's branch reset (or drop and recreate the database);
the next Render start re-creates the schema.

Flight photos go to the private `photos` bucket in Neon Object Storage (declared in
`neon.ts`). Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3` and
`AWS_REGION` on Render (`neon link` writes them to `.env.local`); the API then returns
short-lived signed photo URLs. Without them, photos fall back to local disk.

## Usage flow

Typical usage looks like this:

1. user signs in or registers (password or Google)
2. flights are logged by hand, from SimBrief, or imported from ForeFlight/CSV
3. the logbook, fleet and stats pages show history, totals, currency and maintenance
4. the AI endpoint turns a flight into a short narrative that is saved with it
5. the user can edit flights over time and optionally share a public profile

## Why this project matters technically

AirFleet brings together multiple engineering concerns:

- API design and authentication
- relational database modeling
- frontend-backend integration
- secure env configuration
- AI API integration in real-world app code


## Notes

- The project is intended as a personal engineering exercise and should be hardened before any real-world operational deployment.
