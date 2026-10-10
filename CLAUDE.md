# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

AirFleet is a pilot logbook: a Django REST API (`backend/`) and a Next.js App Router frontend (`frontend/`), deployed as Neon (Postgres + object storage) → Render (API, `render.yaml`) → Vercel (frontend). The root `package.json`/`neon.ts` only hold Neon config; the real JS project is `frontend/`.

## Commands

Backend (Python 3.13 in CI, Django 6; run from `backend/`). Tests need a real Postgres at `DATABASE_URL` (default `postgresql://postgres:postgres@localhost:5432/airfleet`) plus `SECRET_KEY`:

```bash
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000
python manage.py test                                   # full suite
python manage.py test flights.tests.DraftFlightTests    # one class
python manage.py test flights.tests.AirportTests.test_distance  # one test
python manage.py check && python manage.py makemigrations --check --dry-run  # CI also runs these
```

Frontend (Node 22 in CI; run from `frontend/`):

```bash
npm run dev
npm run lint && npm run typecheck && npm run build      # what CI checks
npm run build && PYTHON=../backend/.venv/bin/python npm run test:e2e   # Playwright
npx playwright test e2e/instruction.spec.ts -g "name"   # single e2e test (after a build)
```

Playwright's `webServer` config migrates and starts Django on :8000 and `next start` on :3000 itself, so it runs against a production build and needs Postgres + `DATABASE_URL`/`SECRET_KEY`. `NEXT_PUBLIC_API_URL` is baked in at build time (defaults to `http://localhost:8000`). In this environment Chromium is preinstalled; set `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium` (the config reads it) instead of `playwright install`.

Full stack: `docker compose up --build` (Postgres, Django :8000, Next :3000).

## Backend architecture

- `AirFleet_api/settings.py`: `AUTH_USER_MODEL = 'users.CustomUser'`, JWT-only auth (simplejwt), `DEBUG = False` hard-coded, DB from `DATABASE_URL` via dj-database-url. Throttle scopes (`quick_log`, `lookup`, `invite`, `auth`) are defined here and applied per view. Photos go to S3-compatible Neon Object Storage when `AWS_*` env vars are set, otherwise local disk. New frontend origins must be added to `CORS_ALLOWED_ORIGINS`/`CORS_ALLOWED_ORIGIN_REGEXES`.
- URLs: `users` and `flights` both mount at `/api/`; `instruction` at `/api/instruction/`. `GET /api/rankings/` is public and used as the health check (Render, Playwright).
- `flights/` is the core app; logic is split into plain modules beside the views:
  - `airports.py` — loads the bundled OurAirports extract `data/airports.csv.gz` (ICAO validation, search, great-circle distance).
  - `external.py` — aviationweather.gov METAR and SimBrief lookups (raise `ExternalLookupError` carrying the HTTP status to return).
  - `flight_plans.py` — parses uploaded OFP PDFs (pypdf) anchored on the ICAO `(FPL-...)` message to create draft flights; the PDF isn't stored.
  - `logbook_io.py` — CSV export and AirFleet/ForeFlight CSV import (dedupe, per-row errors).
  - `insights.py` — stats, currency, achievements, maintenance forecast.
  - `realism.py` — the envelope a logged flight has to fit (block speed, duration, dates, landings/approaches per hour). `FlightSerializer.validate` rejects anything outside it, on create, edit and CSV import alike. The limits are physical, not fleet-based — supersonic flights still log fine — so loosen them rather than special-casing an aircraft.
  - `quick_log.py` — reads a pilot's plain-text description into new-flight form fields with an LLM (OpenAI SDK against Gemini, then Groq, from `QUICK_LOG_PROVIDERS`; keys `GEMINI_API_KEY`/`GROQ_API_KEY`). The model's JSON is validated before it reaches the form; nothing is saved. Hidden when no key is set.
- `Flight.is_draft`: drafts must be excluded from totals, currency, rankings and maintenance — remember this when adding any aggregate query.
- A flight reporting its aircraft *Grounded* blocks new flights in that aircraft until maintenance is logged.
- `users/` has no `tests.py`; account/profile/auth tests live in `flights/tests.py` (`AccountTests`, `PublicProfileTests`, etc.). Tests use DRF `APITestCase`; `flights/tests.py` has an `ApiTestCase` base with helpers.
- `instruction/` — instructor links, signatures, endorsements:
  - `models.py` defines `SIGNED_FIELDS`, `flight_snapshot()` and `snapshot_hash()` (SHA-256 of sorted JSON). The flight API recomputes the hash on read; editing any signed field shows the signature as **invalidated** until re-signed or reverted. Adding a field to `SIGNED_FIELDS` changes the hash of existing signatures.
  - Signatures/endorsements are never deleted, only marked withdrawn. Signing requires an active link, dual received time, an unexpired instructor certificate, attestation and the instructor's password.
  - `endorsements.py` holds the endorsement kinds, starter text and expiry rules.
  - "Instructor" is a capability (a certificate on the profile), not an account type.
- Container entrypoint `launcher.sh` runs migrate + collectstatic + gunicorn; migrations run on every Render start.

## Frontend architecture

- Auth is AirFleet's own JWT pair stored in `accessToken`/`refreshToken` cookies (`src/utils/api.ts`: `saveTokens`, auto-refresh on 401 with a single shared in-flight refresh, redirect to `/login` on failure).
- NextAuth (`src/app/api/auth/[...nextauth]/authOptions.ts`) is used only for Google sign-in: its `jwt` callback exchanges the Google ID token with the backend for AirFleet tokens, then `/auth/complete` copies them into cookies and signs out of NextAuth.
- `src/proxy.ts` (Next 16's replacement for `middleware.ts`) gates routes by cookie presence: guest-only pages, public prefixes (`/pilots/`, `/share/`, `/privacy`, password reset…), everything else requires sign-in. Add new public pages to `PUBLIC_PREFIXES`.
- All API calls go through typed functions in `src/utils/api.ts` (types in `src/types/flight.ts`); pages load data with the `useApi(load, key)` hook in `src/utils/useApi.ts`. Use `errorMessage()` to turn DRF error shapes into a sentence.
- Styling is Tailwind v4; maps use Leaflet (`RouteMap.tsx`).

## CI

`.github/workflows/backend.yml` (check, missing-migrations check, tests, Docker build) and `frontend.yml` (lint, typecheck, build, Playwright e2e — also triggered by backend changes). Render deploys the backend from `main` only after CI passes.
