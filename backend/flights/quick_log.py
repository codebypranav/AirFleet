"""Quick log: turn a pilot's plain-text description of a flight into the fields of the new-flight form.

A language model reads the text and answers with JSON; everything it returns is checked here (airports
against the bundled database, times, hour and landing limits) before it reaches the form, and the pilot
reviews the form before anything is saved. Providers are tried in order (settings.QUICK_LOG_PROVIDERS,
any OpenAI-compatible API), so a second one takes over when the first is down or out of free quota.

Times are the pilot's local wall-clock times, like the form's inputs, so they're never converted.
"""
import json
import logging
import re
from datetime import datetime, timedelta

from django.conf import settings
from openai import OpenAI, OpenAIError

from . import airports

logger = logging.getLogger(__name__)

MAX_TEXT = 1000
TIMEOUT_SECONDS = 20
LOCAL_FORMAT = '%Y-%m-%dT%H:%M'

HOUR_FIELDS = {
    'pic_hours': 'pic_time',
    'sic_hours': 'sic_time',
    'dual_received_hours': 'dual_received_time',
    'night_hours': 'night_time',
    'instrument_hours': 'instrument_time',
    'simulated_instrument_hours': 'simulated_instrument_time',
}
COUNT_FIELDS = ('day_landings', 'night_landings', 'approaches')
FLAG_FIELDS = ('cross_country', 'is_simulator')
REGISTRATION_RE = re.compile(r'^[A-Z0-9-]{2,10}$')

SYSTEM_PROMPT = """You turn a pilot's description of a flight into logbook fields. Reply with one JSON object and nothing else, using exactly these keys:

{
  "departure_airport": ICAO code (4 letters, e.g. "KPAO") or null,
  "arrival_airport": ICAO code or null,
  "departure_time": local time "YYYY-MM-DDTHH:MM" or null,
  "arrival_time": local time "YYYY-MM-DDTHH:MM" or null,
  "total_hours": number or null,
  "registration_number": aircraft registration (e.g. "N12345") or null,
  "pic_hours": number or null,
  "sic_hours": number or null,
  "dual_received_hours": number or null,
  "night_hours": number or null,
  "instrument_hours": number or null (actual instrument conditions),
  "simulated_instrument_hours": number or null (under the hood or foggles),
  "day_landings": integer or null,
  "night_landings": integer or null,
  "approaches": integer or null,
  "cross_country": true, false or null,
  "is_simulator": true, false or null,
  "notes": short remarks the pilot made that don't fit another field, or ""
}

Rules:
- Only use what the pilot wrote. Use null for anything not stated or clearly implied; never guess.
- Times are in the pilot's local time. Resolve "today", "yesterday", "this morning" and similar from the current local time given.
- Hours are decimal (1:30 is 1.5). "Solo" or "PIC" without hours means PIC for the whole flight; "dual" or "with my instructor" without hours means dual received for the whole flight.
- "Hood" or "foggles" time is simulated instrument; "actual" or "in the clouds" is instrument.
- A return trip ("and back", "round trip") departs and arrives at the same airport.
- Use an ICAO code only when the pilot wrote it or names an airport you're sure of. If they give a 3-letter code for a US airport, add the K (e.g. "SQL" -> "KSQL").
- "The 172" or similar names one of the pilot's aircraft only when exactly one matches in the fleet list."""


class QuickLogError(Exception):
    """The text couldn't be used; the message is for the pilot."""


class QuickLogUnavailable(Exception):
    """No provider is configured or none answered."""


def enabled():
    return bool(settings.QUICK_LOG_PROVIDERS)


def _local_now(value):
    """The pilot's current local time as sent by the browser ("YYYY-MM-DDTHH:MM"), or server time."""
    try:
        return datetime.strptime(str(value)[:16], LOCAL_FORMAT)
    except (TypeError, ValueError):
        return datetime.now().replace(second=0, microsecond=0)


def build_messages(text, now, fleet):
    fleet_lines = '\n'.join(f'- {reg}' + (f' ({kind})' if kind else '') for reg, kind in fleet) or '- (none saved)'
    user = (
        f"Current local time: {now:%A %Y-%m-%d %H:%M}\n"
        f"The pilot's aircraft:\n{fleet_lines}\n\n"
        f"The pilot's description:\n<<<\n{text}\n>>>"
    )
    return [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user}]


def _parse_json(content):
    content = (content or '').strip()
    # Some models wrap JSON in a Markdown fence despite being asked not to.
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError('expected a JSON object')
    return data


def complete(messages):
    """The first provider's JSON answer; falls through to the next provider on any failure."""
    for provider in settings.QUICK_LOG_PROVIDERS:
        client = OpenAI(api_key=provider['api_key'], base_url=provider['base_url'], timeout=TIMEOUT_SECONDS, max_retries=0)
        try:
            response = client.chat.completions.create(
                model=provider['model'],
                messages=messages,
                response_format={'type': 'json_object'},
                temperature=0,
                max_tokens=1000,
            )
            return _parse_json(response.choices[0].message.content)
        except (OpenAIError, ValueError, IndexError, AttributeError):
            logger.warning('Quick log provider %s failed', provider['name'], exc_info=True)
    raise QuickLogUnavailable


def _hours(value):
    """A number of hours from 0 to 24, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        hours = float(value)
    except ValueError:
        return None
    return hours if 0 <= hours <= 24 else None


def _hm(hours):
    minutes = round(hours * 60)
    return f'{minutes // 60}:{minutes % 60:02d}'


def _local_time(value):
    try:
        return datetime.strptime(str(value)[:16], LOCAL_FORMAT) if value else None
    except ValueError:
        return None


def clean(data, fleet):
    """The form fields worth filling from the model's answer, plus warnings for the pilot."""
    flight, warnings = {}, []

    for field in ('departure_airport', 'arrival_airport'):
        code = str(data.get(field) or '').strip().upper()
        if not code:
            continue
        if len(code) == 4 and airports.get(code):
            flight[field] = code
        else:
            warnings.append(f'Couldn’t find the airport “{code[:12]}”. Enter it yourself.')

    departure, arrival = _local_time(data.get('departure_time')), _local_time(data.get('arrival_time'))
    total = _hours(data.get('total_hours'))
    if departure and not arrival and total:
        arrival = departure + timedelta(hours=total)
    elif arrival and not departure and total:
        departure = arrival - timedelta(hours=total)
    if departure and arrival and arrival <= departure:
        arrival += timedelta(days=1)  # landed after midnight
    if departure and arrival:
        block = (arrival - departure).total_seconds() / 3600
        if block > 24:
            warnings.append('The times didn’t add up. Enter them yourself.')
            departure = arrival = None
        elif total and abs(block - total) > 0.1:
            warnings.append(f'You said {total:g} hours but the times give {block:.1f}. Check them.')
    if departure and arrival:
        flight['departure_time'] = departure.strftime(LOCAL_FORMAT)
        flight['arrival_time'] = arrival.strftime(LOCAL_FORMAT)
    elif total or departure:
        warnings.append('Add the departure and arrival times.')

    registration = re.sub(r'\s', '', str(data.get('registration_number') or '')).upper()
    if registration:
        if REGISTRATION_RE.match(registration):
            flight['registration_number'] = registration
            if fleet and registration not in {reg for reg, _ in fleet}:
                warnings.append(f'{registration} isn’t in your fleet yet.')
        else:
            warnings.append('Couldn’t read the aircraft registration.')

    for source, field in HOUR_FIELDS.items():
        if (hours := _hours(data.get(source))) is not None:
            flight[field] = _hm(hours)

    for field in COUNT_FIELDS:
        value = data.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value == int(value) and 0 <= value <= 99:
            flight[field] = int(value)

    for field in FLAG_FIELDS:
        if isinstance(data.get(field), bool):
            flight[field] = data[field]

    if isinstance(data.get('notes'), str) and data['notes'].strip():
        flight['notes'] = data['notes'].strip()[:500]

    return {'flight': flight, 'warnings': warnings}


def read(text, now, fleet):
    """Form fields and warnings for the pilot's description of a flight.

    fleet is a list of (registration, ICAO type) pairs so "the 172" can resolve to one of their aircraft.
    """
    text = (text or '').strip()
    if not text:
        raise QuickLogError('Describe the flight first.')
    if len(text) > MAX_TEXT:
        raise QuickLogError(f'Keep the description under {MAX_TEXT} characters.')
    if not enabled():
        raise QuickLogUnavailable
    result = clean(complete(build_messages(text, _local_now(now), fleet)), fleet)
    if not result['flight']:
        raise QuickLogError('Couldn’t find any flight details in that. Try including the airports, times or hours.')
    return result
