# AirFleet

**A pilot logbook for real and simulator flying, with AI quick entry and instructor sign-off.**

[Live demo](https://airfleet.vercel.app) · Django REST API + Next.js · GPL-3.0

AirFleet keeps a pilot's flights, aircraft and training records in one place. Log a flight by
hand, describe it in plain words and let AI fill in the form, pull it from SimBrief or a flight
plan PDF, or import a ForeFlight logbook. AirFleet then works out totals, currency, maintenance
due dates and route maps, and lets an instructor sign lessons and give endorsements.

> AirFleet is a personal project, not a certified logbook. It isn't meant to replace an official
> logbook or satisfy regulatory recordkeeping requirements.

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
  map (Leaflet, with a satellite view), passenger/night/IFR currency, and achievements. With AI
  configured, you can also ask in plain words ("How much night time in the C172 since March?",
  "Am I current for passengers at night?"): the model only picks the filters, and the total or
  currency card behind the answer is the same one the page computes from your logbook.
- **Patterns:** what stands out across your flying (a long gap since your last flight, flying
  much less or more than before, night or instrument skills unused for months, most flying on one
  route, an aircraft's inspection or annual coming due). With AI configured, it can also read the
  notes you write after each flight for recurring themes, each linked to the flights behind it.
- **Plan review:** a draft flight is checked against your own logbook before you go, with concrete
  changes where the numbers support one: a block time based on how fast you actually fly that
  aircraft, a time to leave by to land before dark when you aren't night current, a leg much
  longer than any you've logged, a first visit to the destination, passenger and IFR currency on
  the day, the aircraft's maintenance, and current METARs when departure is close.
- **Photos:** attach a photo to a flight; stored privately in Neon Object Storage and served
  through short-lived signed URLs.
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
- **Accounts:** profile editing with a profile picture, password change, password reset by email, optional Google
  sign-in, and opt-in public pilot profiles and shareable flight pages.
- **Flying with friends:** invite crewmates to a logged or live flight by username as Captain (PIC) or
  First officer (SIC). Each crewmate accepts from the Flights page and gets their own copy in their
  logbook, with the block time credited to their role. Notes, photos, landings, approaches,
  simulated instrument and dual received time are not copied, and copies don't sync after accept.
- **Live flights:** start a flight from the Flights page with the route, registration, estimated
  time en route, your role and any crew to invite. A timer runs from take-off, and you, your crew
  and your followers see the flight in a banner on every page (refreshed every 30 seconds) until you
  land. Tick *Only my crew can see this flight* to keep it from followers. Landing
  ends the leg and leaves a draft to finish and log. If you haven't landed 30 minutes past your ETA
  you're asked whether you're still flying; with no answer 2 hours past it, the flight lands itself
  at the ETA. AirFleet is not a search-and-rescue service: a missed check-in alerts nobody.
- **Following:** follow other pilots from their public page or by username on the Following page.
  Public pilots are followed straight away; a private pilot approves or denies the request from their
  profile, where they can also remove followers and block pilots (blocking ends follows both ways and
  stops new ones). Followers see the pilot's live flights in the banner and a feed of their logged
  flights, newest first: route, date, aircraft, block time and distance. A flight's notes are shared
  with followers only when the pilot unticks *Keep my write-up to myself* (ticked by default), and a
  flight can be hidden from followers altogether. Follower counts show on pilot pages, the profile and
  rankings.
- **Comments and likes:** followers who can see a flight, and its pilot, can like it and leave plain-text
  comments (up to 500 characters) under the feed entry and on the pilot's flight page. Replies go one
  level deep, and comments can be liked too. Authors can edit their own comments (shown as *edited*)
  and delete them; the flight's pilot can delete any comment on it. A deleted comment with replies
  stays as *Comment deleted*. Losing access to a flight leaves your comments on it, but you can no
  longer see or edit them.
- **Notifications:** a bell in the nav counts unread follows, follow requests and approvals, comments,
  replies and likes, refreshed every 30 seconds. Opening the list marks them read, and AirFleet keeps
  them for 90 days. AirFleet emails nothing, and your own actions and blocked pilots never notify you.
- **Groups:** join the airline, operator, flight school or community you fly with, and wear it as a
  badge on your profile and your public pilot page. Any pilot can create up to five groups and becomes
  their admin; official organizations are set up by AirFleet staff, who also gather airlines into
  alliances (Star Alliance and the like). A community group is joined on the spot, and joining one
  that has been left without an admin makes you its admin, while an official group's admins approve
  or decline each request, promote, demote and remove members, and edit the group. A group page lists
  its members, counting without naming the ones whose profile is private, and an alliance page lists
  its member airlines with their pilot counts.
- **Rankings:** by flights, time, distance, longest flight and airports visited, for all
  time, this year or this month.
- **Instructor sign-off:** a pilot links with their instructor by invitation (either side
  invites, the other accepts), and the instructor signs lessons with dual received time, gives
  endorsements (solo, checkride, flight review and so on), and can withdraw either. A student
  progress page adds up each linked student's logged hours against the private pilot minimums of
  14 CFR 61.109(a) and lists the endorsements and hours still missing.
  Instructing is a capability, not an account type: anyone who adds an instructor certificate
  to their profile can be invited as one and still logs their own flights. See
  [Instructor sign-off](#instructor-sign-off).
- **Privacy:** a `/privacy` notice of what is stored and which services see it, and account
  deletion from the profile page that erases the pilot's flights, aircraft, photos, likes, notifications
  and comments (a comment with replies stays as *Comment deleted*).

## Technical architecture

### Backend (`backend/`)
- Python 3.12+, Django 6, Django REST Framework
- PostgreSQL via `DATABASE_URL`
- JWT authentication (`djangorestframework-simplejwt`), plus Google sign-in
- OpenAI-compatible LLM client (Gemini, then Groq, free tiers) for quick log
- `pypdf` for flight plan PDFs, `django-storages` for S3-compatible photo storage
- Gunicorn in a Docker container on Render

The backend is organized around Django apps:

- `AirFleet_api/` — settings, URLs, throttle scopes
- `flights/` — flights, aircraft, insights, imports/exports, airport data, quick log, weather and
  SimBrief lookups, flight plan parsing
- `users/` — accounts, profiles, password reset, public pilot pages
- `instruction/` — instructor links, lesson signatures, endorsements and student progress
- `groups/` — pilot groups (airlines, operators, flight schools, alliances, communities) and their memberships

### Frontend (`frontend/`)
- Next.js 16 (App Router), React 19, TypeScript
- Tailwind CSS 4
- Leaflet route maps
- NextAuth only for Google sign-in; AirFleet's own JWTs live in cookies and are refreshed
  automatically
- Typed API client in `src/utils/api.ts`

### Infrastructure
- Neon: Postgres and object storage (photos)
- Render: the Django API (`render.yaml`)
- Vercel: the Next.js frontend
- Docker Compose for local development; GitHub Actions for CI

## Core implementation details

### Authentication
The client signs in with a password (or Google, whose ID token the backend exchanges for its own
tokens) and gets an access/refresh token pair. The frontend stores them in cookies, sends the access
token on each request, and refreshes it once on a 401 before sending the user back to `/login`.
`AUTH_USER_MODEL` is `users.CustomUser`; token lifetimes, throttles and CORS origins are set in
`backend/AirFleet_api/settings.py`.

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

### Ask your logbook
`POST /api/stats/ask/` takes `question` (up to 300 characters) and `now`, and answers with the
filters it used plus one total from the stats page or one currency card. The model's only job is to
turn the question into those filters — which stats total, a date range, an aircraft from the pilot's
own fleet, an airport, whether simulator sessions count, or a currency check — so no wording or
number from the model reaches the pilot. Filters it can't use are dropped with a warning (an aircraft
that isn't in the fleet, an unknown airport, dates that don't read or run backwards), a currency
question is answered as of today across all aircraft, and a question that fits none of the filters
gets a 422 with examples rather than an approximation. Drafts stay out, as everywhere else. Asking
shares the quick log providers and rate limit, and the panel is hidden when quick log is.

### Patterns and plan review
`GET /api/insights/` returns findings computed from the logbook in `flights/patterns.py`, each with
the numbers behind it. `POST /api/insights/themes/` sends the notes of the pilot's last 40 logged
flights to the quick log providers and returns recurring themes. A theme is kept only if it cites at
least two of the flights the model was shown; it shares quick log's rate limit.

`GET /api/flights/<id>/review/` checks a draft flight in `flights/plan_review.py`. This part
deliberately uses no language model. Every suggestion comes from arithmetic the pilot can check: their
average block speed in the aircraft (or type), their longest leg, the airports they've logged,
currency on the day of the flight, the aircraft's maintenance, the sun's position at the destination
for night arrivals, and the current METAR when the flight leaves within three hours. It doesn't
replace a briefing: forecasts, NOTAMs, fuel and performance are left to the pilot.

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
instructor sees in full the ones they gave, and the instructor can withdraw one the same way as a signature.

**Student progress** (`GET /api/instruction/dashboard/`) shows an instructor every student on an
active link, measured against the private pilot minimums of 14 CFR 61.109(a) for airplane
single-engine land. The rows are a hard-coded table of one rule each in
`instruction/requirements.py` — total, dual, dual cross-country, dual night, night landings with an
instructor, dual simulated instrument, dual in the last two calendar months, solo and solo
cross-country — summed over the student's logged flights, simulator sessions left out, with the
signed share of the dual shown alongside it. The server writes the "missing" sentences, so the page
holds no rules of its own. Three requirements a logbook can't express (the 100 nm night
cross-country, the 150 nm solo cross-country, three solo full-stop landings at a towered airport)
are listed as things to check in the logbook rather than counted, and the six endorsements the
certificate needs are shown as current, expired or missing from **any** instructor, not only the one
looking.

The totals are a deliberate privacy trade, set out on `/privacy`: they cover all of the student's
logged flights, including solo and other time not flown with this instructor, but the flights behind
them stay hidden. The page names its approximations — solo is PIC time on a flight with no dual
received, dual night and dual simulated instrument count the smaller of that time and the flight's
dual, and aircraft class isn't filtered — and it is a guide to what to fly next, not a checkride
sign-off.

The **CSV export** adds `instructor_name`, `instructor_certificate`, `instructor_signed_at` and
`signature_status` (`valid`, `invalidated` or `withdrawn`) from each flight's latest signature. They are
ignored on import: a signature can't be imported.

AirFleet calls this **instructor-verified**. It is not presented as a signature that satisfies
14 CFR 61.51(h) or the FAA's guidance on electronic signatures (AC 120-78A), and the hash is change
detection, not tamper-proofing against someone with database access.

## Repository structure

```text
.github/workflows/  # backend and frontend CI
backend/
  AirFleet_api/
  flights/
  groups/
  instruction/
  users/
  flights/data/airports.csv.gz
  Dockerfile
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
npx playwright install chromium   # or set PLAYWRIGHT_CHROMIUM_PATH to an existing Chromium
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
GEMINI_API_KEY=...                        # quick log, note themes and asking, from aistudio.google.com (free tier)
GROQ_API_KEY=...                          # quick log fallback, from console.groq.com (free tier)
GEMINI_MODEL=gemini-flash-lite-latest     # optional overrides of the quick log models
GROQ_MODEL=openai/gpt-oss-20b
QUICK_LOG_RATE=30/hour                    # quick log limit per user

# Frontend
GOOGLE_CLIENT_ID=...                      # with GOOGLE_CLIENT_SECRET, shows "Continue with Google"
GOOGLE_CLIENT_SECRET=...
API_URL=...                               # API origin for server-side calls, if it differs from NEXT_PUBLIC_API_URL
NEXT_PUBLIC_ENABLE_DEBUG=true             # turns on the /debug connection page
NEXT_PUBLIC_PRIVACY_CONTACT=you@example.com  # shown on /privacy for data requests, and on a group page for making it official
NEXT_PUBLIC_ARCGIS_API_KEY=...            # optional: high-res Esri satellite view (free tier, 2M tiles/month); without it satellite uses NASA Blue Marble
NEXT_PUBLIC_CARTO_API_KEY=...             # dark basemap tiles (free key from carto.com/basemaps/apikey); without it the map falls back to OpenStreetMap
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

## License

[GPL-3.0](LICENSE)
