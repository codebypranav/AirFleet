"""Read-only views over a pilot's logbook: totals, currency, maintenance forecasts and achievements."""
import calendar
import math
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from . import airports

ZERO = timedelta(0)


def hours(duration):
    return round((duration or ZERO).total_seconds() / 3600, 1)


def airports_visited(flights):
    codes = set()
    for dep, arr in flights.values_list('departure_airport', 'arrival_airport'):
        codes.update((dep, arr))
    return codes


def summary(flights):
    totals = flights.aggregate(
        flights=Count('id'),
        total_time=Sum('total_time'),
        distance=Sum('distance'),
        pic_time=Sum('pic_time'),
        night_time=Sum('night_time'),
        instrument_time=Sum('instrument_time'),
        simulated_instrument_time=Sum('simulated_instrument_time'),
        day_landings=Sum('day_landings'),
        night_landings=Sum('night_landings'),
        approaches=Sum('approaches'),
        cross_country=Count('id', filter=Q(cross_country=True)),
        simulator=Count('id', filter=Q(is_simulator=True)),
    )
    visited = airports_visited(flights)
    countries = {a.country for a in map(airports.get, visited) if a}

    today = timezone.now().date()
    first_month = date(today.year - (today.month <= 11), (today.month - 12) % 12 + 1, 1)
    monthly = {
        row['month'].date().replace(day=1) if hasattr(row['month'], 'date') else row['month']: row
        for row in flights.filter(departure_time__date__gte=first_month)
        .annotate(month=TruncMonth('departure_time'))
        .values('month')
        .annotate(flights=Count('id'), total_time=Sum('total_time'), distance=Sum('distance'))
    }
    by_month = []
    month = first_month
    for _ in range(12):
        row = monthly.get(month, {})
        by_month.append({
            'month': month.isoformat(),
            'flights': row.get('flights', 0),
            'hours': hours(row.get('total_time')),
            'distance': row.get('distance') or 0,
        })
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)

    top_routes = [
        {'from': r['departure_airport'], 'to': r['arrival_airport'], 'flights': r['flights'], 'hours': hours(r['total_time'])}
        for r in flights.values('departure_airport', 'arrival_airport')
        .annotate(flights=Count('id'), total_time=Sum('total_time'))
        .order_by('-flights', '-total_time')[:5]
    ]
    top_aircraft = [
        {'registration': r['registration_number'], 'type_code': r['aircraft__type_code'] or '', 'flights': r['flights'], 'hours': hours(r['total_time'])}
        for r in flights.values('registration_number', 'aircraft__type_code')
        .annotate(flights=Count('id'), total_time=Sum('total_time'))
        .order_by('-total_time', '-flights')[:5]
    ]

    return {
        'totals': {
            'flights': totals['flights'],
            'hours': hours(totals['total_time']),
            'distance': totals['distance'] or 0,
            'pic_hours': hours(totals['pic_time']),
            'night_hours': hours(totals['night_time']),
            'instrument_hours': hours(totals['instrument_time']),
            'simulated_instrument_hours': hours(totals['simulated_instrument_time']),
            'landings': (totals['day_landings'] or 0) + (totals['night_landings'] or 0),
            'night_landings': totals['night_landings'] or 0,
            'approaches': totals['approaches'] or 0,
            'cross_country_flights': totals['cross_country'],
            'simulator_flights': totals['simulator'],
            'airframes': flights.values('registration_number').distinct().count(),
            'airports': len(visited),
            'countries': len(countries),
        },
        'by_month': by_month,
        'top_routes': top_routes,
        'top_aircraft': top_aircraft,
    }


def routes(flights):
    """Distinct routes with coordinates, for drawing the route map."""
    rows = (
        flights.values('departure_airport', 'arrival_airport')
        .annotate(flights=Count('id'), total_time=Sum('total_time'))
        .order_by('-flights')
    )
    result, seen = [], {}
    for r in rows:
        dep, arr = airports.get(r['departure_airport']), airports.get(r['arrival_airport'])
        if not dep or not arr:
            continue
        seen[dep.code], seen[arr.code] = dep, arr
        result.append({'from': dep.code, 'to': arr.code, 'flights': r['flights'], 'hours': hours(r['total_time'])})
    return {'routes': result, 'airports': [a.as_dict() for a in seen.values()]}


def _add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def _currency(key, label, rule, events, needed, expiry, window_start, today):
    """events: (date, count) pairs, newest first. Currency runs from the event that completes `needed`."""
    running, expires_on = 0, None
    for day, count in events:
        running += count
        if running >= needed:
            expires_on = expiry(day)
            break
    in_window = sum(count for day, count in events if day >= window_start)
    if expires_on is None or expires_on < today:
        state = 'lapsed'
    elif (expires_on - today).days <= 14:
        state = 'expiring'
    else:
        state = 'current'
    return {
        'key': key,
        'label': label,
        'rule': rule,
        'needed': needed,
        'count_in_window': in_window,
        'expires_on': expires_on.isoformat() if expires_on else None,
        'days_left': (expires_on - today).days if expires_on and expires_on >= today else 0,
        'status': state,
    }


def currency(flights, today=None):
    """FAR 61.57-style currency. Simulator sessions count for instrument currency only."""
    today = today or timezone.now().date()
    ordered = flights.order_by('-departure_time')
    real = ordered.filter(is_simulator=False)
    day_events = [(f.departure_time.date(), f.day_landings + f.night_landings) for f in real if f.day_landings + f.night_landings]
    night_events = [(f.departure_time.date(), f.night_landings) for f in real if f.night_landings]
    ifr_events = [(f.departure_time.date(), f.approaches) for f in ordered if f.approaches]

    return [
        _currency('passenger_day', 'Passengers (day)', '3 takeoffs and landings in the last 90 days',
                  day_events, 3, lambda d: d + timedelta(days=90), today - timedelta(days=90), today),
        _currency('passenger_night', 'Passengers (night)', '3 full-stop night landings in the last 90 days',
                  night_events, 3, lambda d: d + timedelta(days=90), today - timedelta(days=90), today),
        _currency('instrument', 'Instrument (IFR)', '6 approaches in the last 6 calendar months',
                  ifr_events, 6, lambda d: _add_months(d, 6), _add_months(today, -7) + timedelta(days=1), today),
    ]


FORECAST_WINDOW_DAYS = 90


def maintenance_forecast(hours_since, interval, recent_hours, annual_due, today, window_days=FORECAST_WINDOW_DAYS):
    """Project the hours-based inspection from how much the aircraft flew in the last `window_days`.

    No model: hours remaining divided by the recent daily rate. With no recent flying there's no
    date for the inspection. Whichever of it and the annual comes first is the next one due.
    """
    remaining = max(interval - hours_since, 0)
    per_day = recent_hours / window_days
    if remaining == 0:
        inspection_due_on = today
    elif per_day > 0:
        inspection_due_on = today + timedelta(days=math.ceil(round(remaining / per_day, 6)))
    else:
        inspection_due_on = None

    upcoming = [(d, kind) for d, kind in ((inspection_due_on, 'inspection'), (annual_due, 'annual')) if d]
    next_due = min(upcoming) if upcoming else None
    return {
        'window_days': window_days,
        'hours_per_week': round(per_day * 7, 1),
        'hours_remaining': round(remaining, 1),
        'inspection_due_on': inspection_due_on.isoformat() if inspection_due_on else None,
        'next_due': {'kind': next_due[1], 'date': next_due[0].isoformat()} if next_due else None,
    }

ACHIEVEMENTS = [
    ('first_flight', 'First page', 'Log your first flight', lambda s, f: s['flights'] >= 1),
    ('flights_10', 'Regular', 'Log 10 flights', lambda s, f: s['flights'] >= 10),
    ('flights_100', 'Centurion', 'Log 100 flights', lambda s, f: s['flights'] >= 100),
    ('hours_10', 'Ten hours', 'Fly 10 hours in total', lambda s, f: s['seconds'] >= 10 * 3600),
    ('hours_100', 'Hundred hours', 'Fly 100 hours in total', lambda s, f: s['seconds'] >= 100 * 3600),
    ('hours_500', 'Five hundred', 'Fly 500 hours in total', lambda s, f: s['seconds'] >= 500 * 3600),
    ('hours_1000', 'Thousand-hour pilot', 'Fly 1,000 hours in total', lambda s, f: s['seconds'] >= 1000 * 3600),
    ('first_night', 'Night owl', 'Log your first night flight', lambda s, f: f.night_time > ZERO or f.night_landings > 0),
    ('first_xc', 'Cross-country', 'Log your first cross-country flight', lambda s, f: f.cross_country),
    ('first_ifr', 'In the clouds', 'Log actual instrument time or an approach', lambda s, f: f.instrument_time > ZERO or f.approaches > 0),
    ('airports_10', 'Explorer', 'Visit 10 different airports', lambda s, f: len(s['airports']) >= 10),
    ('airports_50', 'Globetrotter', 'Visit 50 different airports', lambda s, f: len(s['airports']) >= 50),
    ('countries_3', 'Border hopper', 'Land in 3 different countries', lambda s, f: len(s['countries']) >= 3),
    ('long_haul', 'Long haul', 'Fly 1,000 nm in a single flight', lambda s, f: f.distance >= 1000),
    ('marathon', 'Marathon', 'Spend 8 hours on a single flight', lambda s, f: f.total_time >= timedelta(hours=8)),
]


def achievements(flights):
    state = {'flights': 0, 'seconds': 0, 'airports': set(), 'countries': set()}
    earned = {}
    for flight in flights.order_by('departure_time'):
        state['flights'] += 1
        state['seconds'] += flight.total_time.total_seconds()
        for code in (flight.departure_airport, flight.arrival_airport):
            state['airports'].add(code)
            airport = airports.get(code)
            if airport:
                state['countries'].add(airport.country)
        for key, _, _, test in ACHIEVEMENTS:
            if key not in earned and test(state, flight):
                earned[key] = {'earned_at': flight.departure_time.isoformat(), 'flight_id': flight.id}
        if len(earned) == len(ACHIEVEMENTS):
            break
    return [
        {'key': key, 'title': title, 'description': description, 'earned': key in earned, **earned.get(key, {})}
        for key, title, description, _ in ACHIEVEMENTS
    ]
