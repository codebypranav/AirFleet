# AirFleet

AirFleet is a personal aviation operations and flight logging project that combines a Django backend, a Next.js frontend, and AI-assisted flight entry. The application is designed to help pilots or sim pilots store flight entries, manage user accounts, and log a flight by describing it in plain words.

## Product goal

The system is meant to function as a lightweight aviation workspace with:

- flight record storage
- user-specific flight history
- JWT-based authentication
- AI quick log: describe a flight in plain words to fill in the logbook entry
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
  flights in it until maintenance is logged. The next inspection is forecast from the last
  90 days of flying (hours left ÷ recent rate), alongside the annual.
- **Stats:** totals, hours per month, most-flown routes and aircraft, a great-circle route
  map (Leaflet), passenger/night/IFR currency, and achievements.
- **Quick log:** describe a flight in your own words ("KPAO to KSQL and back, 1.4, 3 landings,
  0.3 hood") and AI fills in the new-flight form for you to check before saving. Uses free-tier
  Gemini, with Groq as a fallback; hidden when neither is configured.
- **Weather and SimBrief:** fetch the departure METAR (aviationweather.gov, last ~15 days)
  or prefill a flight from your latest SimBrief flight plan.
- **Flight plan PDFs:** upload a SimBrief OFP, or any plan that includes an ICAO flight plan, to
  start a draft entry: airports, planned OUT/IN times, registration, type, route and distance are
  read from the PDF (anchored on the ICAO `(FPL-...)` message). Drafts stay out of totals, currency, rankings and maintenance until you add
  the actual times and untick *Draft*. The PDF itself isn't stored.
- **Import/export:** CSV export of the logbook (or a filtered slice), and import of AirFleet
  CSVs or ForeFlight logbook exports. Duplicates are skipped and bad rows reported.
- **Accounts:** profile editing, password change, password reset by email, optional Google
  sign-in, and opt-in public pilot profiles and shareable flight pages.
- **Rankings:** by flights, time, distance, longest flight and airports visited, for all
  time, this year or this month.
- **Instructor sign-off:** a pilot links with their instructor by invitation (either side
  invites, the other accepts), and the instructor signs lessons with dual received time, gives
  endorsements (solo, checkride, flight review and so on), and can withdraw either.
  Instructing is a capability, not an account type: anyone who adds an instructor certificate
  to their profile can be invited as one and still logs their own flights. See
  [Instructor sign-off](#instructor-sign-off).
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
- OpenAI-compatible LLM client (Gemini, Groq free tiers) for quick log

The backend is organized around Django apps:

- `backend/AirFleet_api/` — project configuration and settings
- `backend/flights/` — flight models, serializers, and API logic
- `backend/users/` — user auth and profile logic
- `backend/instruction/` — instructor links and lesson sign-offs

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
- `QuickLogView` reads a plain-text description of a flight into form fields with an LLM

This is the main business logic for recording aviation events and making them quick to enter.

### Quick log
`POST /api/flights/quick-log/` takes `text` (a pilot's own description of a flight, up to 1,000
characters) and `now` (their local time, so "this morning" resolves) and returns form fields plus
warnings; nothing is saved. A language model reads the text and answers in JSON, which
`flights/quick_log.py` checks before it reaches the form: airports must be in the bundled database,
hours must be 0–24, arrival is worked out from departure plus total time, and disagreements are
flagged. The prompt also lists the pilot's fleet so "the 172" can resolve to a registration.

Providers are any OpenAI-compatible API, tried in order: Gemini (`GEMINI_API_KEY`) then Groq
(`GROQ_API_KEY`). Both have free tiers, so the second takes over when the first is down or out of
its daily quota. `GET /api/flights/quick-log/` returns `{"enabled": ...}`, and the form hides quick
log when neither key is set. Requests are limited per user (`QUICK_LOG_RATE`, default `30/hour`).

### Instructor sign-off
`InstructorLink` joins a student and an instructor. Either pilot invites the other by username or
email (`POST /api/instruction/links/`); the invitee gets an email and accepts on the Instruction page.
Either side can decline or unlink. While linked, the instructor sees the student's flights that have
dual received time, limited to the fields they would sign (`GET /api/instruction/links/<id>/flights/`).

Signing (`POST /api/instruction/flights/<id>/sign/`) needs an active link, dual received time on the
flight, a certificate number on the instructor's profile that hasn't expired, a ticked attestation and
the instructor's password. Each `Signature` stores:

- the instructor's name, certificate number and expiry at the time of signing
- the attestation text they agreed to, and their remarks
- a snapshot of the signed fields (route, times, aircraft, logbook columns, landings, approaches,
  cross-country, simulator, plus the flight and pilot ids) and its SHA-256 hash

The flight API recomputes the hash from the current entry. If the student edits a signed field, the
signature shows as **invalidated**, with the fields that changed, until the instructor signs again (or
the values are put back). Notes, photos and weather aren't signed and can change freely. A
signature stays on the student's flight if the instructor unlinks or deletes their account.

The instructor who signed can **withdraw** a signature (`POST /api/instruction/signatures/<id>/withdraw/`)
with an optional reason and their password, even after unlinking. Nothing is deleted: the signature
is marked withdrawn, the student sees when and why, and the lesson can be signed again.

**Endorsements** (`Endorsement`) are given by a linked instructor to their student
(`POST /api/instruction/links/<id>/endorsements/`): pre-solo, solo, solo cross-country, knowledge test,
practical test, flight review, IPC, complex, high-performance, tailwheel, or a custom one. Each kind
has a plain-language starting draft (`instruction/endorsements.py`) that the instructor edits before
signing; it is not the wording of AC 61-65. An endorsement records the same instructor details as a
signature, the date given, and an expiry where the kind has one (solo: 90 days; practical test: 2
calendar months; flight review: 24 calendar months). Students see theirs on the Instruction page, the
instructor sees the ones they gave, and the instructor can withdraw one the same way as a signature.

The **CSV export** adds `instructor_name`, `instructor_certificate`, `instructor_signed_at` and
`signature_status` (`valid`, `invalidated` or `withdrawn`) from each flight's latest signature. They are
ignored on import: a signature can't be imported.

AirFleet calls this **instructor-verified**. It is not presented as a signature that satisfies
14 CFR 61.51(h) or the FAA's guidance on electronic signatures (AC 120-78A), and the hash is change
detection, not tamper-proofing against someone with database access.

## Repository structure

```text
backend/
  AirFleet_api/
  flights/
  instruction/
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
GEMINI_API_KEY=...                        # quick log, from aistudio.google.com (free tier)
GROQ_API_KEY=...                          # quick log fallback, from console.groq.com (free tier)
GEMINI_MODEL=gemini-flash-lite-latest     # optional overrides of the quick log models
GROQ_MODEL=openai/gpt-oss-20b
QUICK_LOG_RATE=30/hour                    # quick log limit per user

# Frontend
GOOGLE_CLIENT_ID=...                      # with GOOGLE_CLIENT_SECRET, shows "Continue with Google"
GOOGLE_CLIENT_SECRET=...
API_URL=...                               # API origin for server-side calls, if it differs from NEXT_PUBLIC_API_URL
NEXT_PUBLIC_ENABLE_DEBUG=true             # turns on the /debug connection page
NEXT_PUBLIC_PRIVACY_CONTACT=you@example.com  # shown on /privacy for data requests
NEXT_PUBLIC_ARCGIS_API_KEY=...            # optional: high-res Esri satellite view (free tier, 2M tiles/month); without it satellite uses NASA Blue Marble
```

For Google sign-in, create an OAuth client (Web application) in Google Cloud and add
`<frontend URL>/api/auth/callback/google` as an authorized redirect URI.

## Deployment

The demo runs entirely on free tiers: Neon (Postgres), Render (Django API) and Vercel (Next.js).

1. **Database (Neon):** create a project at neon.com and copy its connection string
   (it ends in `?sslmode=require`).
2. **Backend (Render):** New → Blueprint → select this repo. Render reads `render.yaml`
   and asks for `DATABASE_URL` (the Neon string) and the optional quick log keys `GEMINI_API_KEY`
   and `GROQ_API_KEY`; `SECRET_KEY` is generated.
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
2. flights are logged by hand, by describing them (quick log), from SimBrief, or imported from ForeFlight/CSV
3. the logbook, fleet and stats pages show history, totals, currency and maintenance
4. the user can edit flights over time and optionally share a public profile

## Why this project matters technically

AirFleet brings together multiple engineering concerns:

- API design and authentication
- relational database modeling
- frontend-backend integration
- secure env configuration
- AI API integration in real-world app code


## Notes

- The project is intended as a personal engineering exercise and should be hardened before any real-world operational deployment.
