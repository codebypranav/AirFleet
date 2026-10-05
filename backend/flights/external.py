"""Lookups against public aviation services: aviationweather.gov METARs and SimBrief OFPs."""
from datetime import datetime, timedelta, timezone as dt_timezone

import requests

METAR_URL = 'https://aviationweather.gov/api/data/metar'
SIMBRIEF_URL = 'https://www.simbrief.com/api/xml.fetcher.php'
TIMEOUT = 8
HEADERS = {'User-Agent': 'AirFleet logbook (+https://github.com/codebypranav/AirFleet)'}


class ExternalLookupError(Exception):
    """A lookup failed. `status` is the HTTP status the API should answer with."""

    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def metar(airport, at=None):
    """The METAR observed closest to `at` (default: now). aviationweather.gov keeps about 15 days."""
    at = at or datetime.now(dt_timezone.utc)
    params = {'ids': airport, 'format': 'json', 'hours': 3}
    if datetime.now(dt_timezone.utc) - at > timedelta(hours=1):
        params['date'] = (at + timedelta(hours=1, minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        response = requests.get(METAR_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        reports = response.json() if response.content else []
    except (requests.RequestException, ValueError) as e:
        raise ExternalLookupError('The weather service is unavailable right now.') from e
    if not isinstance(reports, list) or not reports:
        raise ExternalLookupError(f'No METAR found for {airport} around that time. Reports are only kept for about two weeks.', status=404)
    target = at.timestamp()
    best = min(reports, key=lambda r: abs((r.get('obsTime') or 0) - target))
    return {
        'airport': airport,
        'raw': best.get('rawOb', ''),
        'observed_at': datetime.fromtimestamp(best['obsTime'], dt_timezone.utc).isoformat() if best.get('obsTime') else None,
        'flight_category': best.get('fltCat'),
    }


def _epoch(value):
    try:
        return datetime.fromtimestamp(int(value), dt_timezone.utc)
    except (TypeError, ValueError):
        return None


def simbrief_latest(username):
    """A flight draft from the pilot's most recent SimBrief OFP."""
    try:
        response = requests.get(SIMBRIEF_URL, params={'username': username, 'json': 1}, headers=HEADERS, timeout=TIMEOUT)
        data = response.json()
    except (requests.RequestException, ValueError) as e:
        raise ExternalLookupError('SimBrief is unavailable right now.') from e

    status = (data.get('fetch') or {}).get('status', '')
    if status != 'Success':
        raise ExternalLookupError(f'SimBrief: {status or "no flight plan found"}', status=404)

    times = data.get('times') or {}
    general = data.get('general') or {}
    aircraft = data.get('aircraft') or {}
    weather = data.get('weather') or {}
    departure = _epoch(times.get('sched_out'))
    arrival = _epoch(times.get('sched_in'))
    distance = general.get('route_distance') or general.get('air_distance') or 0
    metar_text = weather.get('orig_metar')
    return {
        'departure_airport': (data.get('origin') or {}).get('icao_code', ''),
        'arrival_airport': (data.get('destination') or {}).get('icao_code', ''),
        'departure_time': departure.isoformat() if departure else None,
        'arrival_time': arrival.isoformat() if arrival else None,
        'registration_number': (aircraft.get('reg') or '')[:10],
        'aircraft_type': aircraft.get('icaocode', ''),
        'flight_plan': general.get('route', ''),
        'distance': int(float(distance)) if str(distance).replace('.', '', 1).isdigit() else 0,
        'weather_conditions': ' '.join(metar_text.split()) if isinstance(metar_text, str) else '',
        'is_simulator': True,
    }
