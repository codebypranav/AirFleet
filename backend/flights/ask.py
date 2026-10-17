from django.db.models import Q
from django.utils.dateparse import parse_date

from . import airports, insights, quick_log

MAX_QUESTION = 300

METRICS = {
    'flights': 'Flights',
    'hours': 'Total hours',
    'pic_hours': 'PIC hours',
    'night_hours': 'Night hours',
    'instrument_hours': 'Actual instrument hours',
    'simulated_instrument_hours': 'Simulated instrument hours',
    'landings': 'Landings',
    'night_landings': 'Night landings',
    'approaches': 'Approaches',
    'cross_country_flights': 'Cross-country flights',
    'simulator_flights': 'Simulator sessions',
    'distance': 'Distance (nm)',
    'airframes': 'Aircraft flown',
    'airports': 'Airports visited',
    'countries': 'Countries visited',
}
CURRENCY = ('passenger_day', 'passenger_night', 'instrument')

SYSTEM_PROMPT = f"""You turn a pilot's question about their own logbook into filters. You never answer it yourself. Reply with one JSON object and nothing else:

{{
  "metric": one of {', '.join(METRICS)}, or null,
  "currency": one of {', '.join(CURRENCY)}, or null,
  "from": first day to count, "YYYY-MM-DD", or null,
  "to": last day to count, "YYYY-MM-DD", or null,
  "aircraft": a registration or ICAO type from the pilot's aircraft list, or null,
  "airport": a 4-letter ICAO code, or null,
  "simulator": true for simulator sessions only, false to leave them out, or null
}}

Rules:
- Use "currency" for questions about being current or legal to fly: passenger_day (carrying passengers), passenger_night (passengers at night), instrument (IFR). Otherwise use "metric".
- "Time" or "hours" alone means hours. "Night time" is night_hours, "PIC" is pic_hours, "actual" or "IMC" is instrument_hours, "hood" or "foggles" is simulated_instrument_hours.
- Resolve "since March", "last year", "this month" from today's date. A month already past this year means this year's.
- If the question fits none of these, set both metric and currency to null."""


class AskError(Exception):
    pass


def build_messages(question, now, fleet):
    fleet_lines = '\n'.join(f'- {reg}' + (f' ({kind})' if kind else '') for reg, kind in fleet) or '- (none saved)'
    user = (
        f"Today: {now:%A %Y-%m-%d}\n"
        f"The pilot's aircraft:\n{fleet_lines}\n\n"
        f"The question:\n<<<\n{question}\n>>>"
    )
    return [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user}]


def _date(value):
    try:
        return parse_date(value) if isinstance(value, str) else None
    except ValueError:
        return None


def clean(data, fleet):
    data = data if isinstance(data, dict) else {}
    if data.get('currency') in CURRENCY:
        ignored = any(data.get(k) for k in ('from', 'to', 'aircraft', 'airport'))
        return {'currency': data['currency'], 'warnings': ['Currency is as of today, across all your aircraft.'] if ignored else []}
    if data.get('metric') not in METRICS:
        raise AskError('I can answer totals and currency, e.g. “How much night time in the C172 since March?” or “Am I current for passengers at night?”')

    filters, warnings, registrations = {}, [], None
    start, end = _date(data.get('from')), _date(data.get('to'))
    if (data.get('from') and not start) or (data.get('to') and not end):
        warnings.append('I couldn’t read the dates in that, so this covers all time.')
        start = end = None
    elif start and end and start > end:
        warnings.append('The dates were the wrong way round, so this covers all time.')
    else:
        filters.update({k: d.isoformat() for k, d in (('from', start), ('to', end)) if d})

    if isinstance(data.get('aircraft'), str) and data['aircraft'].strip():
        aircraft = data['aircraft'].strip().upper()
        registrations = [reg for reg, kind in fleet if aircraft in (reg.upper(), (kind or '').upper())]
        if registrations:
            filters['aircraft'] = aircraft
        else:
            registrations = None
            warnings.append(f'{aircraft[:12]} isn’t one of your aircraft, so this covers all of them.')

    if isinstance(data.get('airport'), str) and data['airport'].strip():
        code = data['airport'].strip().upper()
        if airports.get(code):
            filters['airport'] = code
        else:
            warnings.append(f'{code[:12]} isn’t an airport I know, so this covers all airports.')

    if isinstance(data.get('simulator'), bool):
        filters['simulator'] = data['simulator']

    return {'metric': data['metric'], 'filters': filters, 'registrations': registrations, 'warnings': warnings}


def read(question, now, fleet):
    question = (question or '').strip()
    if not question:
        raise AskError('Ask a question first.')
    if len(question) > MAX_QUESTION:
        raise AskError(f'Keep the question under {MAX_QUESTION} characters.')
    if not quick_log.enabled():
        raise quick_log.QuickLogUnavailable
    return clean(quick_log.complete(build_messages(question, quick_log.local_now(now), fleet)), fleet)


def answer(flights, asked):
    if 'currency' in asked:
        card = next(c for c in insights.currency(flights) if c['key'] == asked['currency'])
        return {'kind': 'currency', 'currency': card, 'warnings': asked['warnings']}

    filters = asked['filters']
    if 'from' in filters:
        flights = flights.filter(departure_time__date__gte=filters['from'])
    if 'to' in filters:
        flights = flights.filter(departure_time__date__lte=filters['to'])
    if asked['registrations']:
        flights = flights.filter(registration_number__in=asked['registrations'])
    if 'airport' in filters:
        flights = flights.filter(Q(departure_airport=filters['airport']) | Q(arrival_airport=filters['airport']))
    if 'simulator' in filters:
        flights = flights.filter(is_simulator=filters['simulator'])
    return {
        'kind': 'total',
        'metric': asked['metric'],
        'label': METRICS[asked['metric']],
        'value': insights.summary(flights)['totals'][asked['metric']],
        'filters': filters,
        'warnings': asked['warnings'],
    }
