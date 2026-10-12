"""Check a planned (draft) flight against the pilot's own logbook and fleet, and suggest changes to the plan.

Each check compares the plan with something the pilot can verify: how fast they actually fly that
aircraft, the longest leg they've logged, the airports they know, their currency on the day of the
flight, their aircraft's maintenance and, close to departure, the current weather. A suggestion is only
made when there's arithmetic behind it (a block time from their own speed, a time to leave by to land
before dark), so none of it comes from a language model: a wrong plan change costs more than a missing one.

It isn't a briefing. Weather forecasts, NOTAMs, fuel and performance stay the pilot's job.
"""
import math
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db.models import Count, Max, Sum

from . import airports, external, insights

TONE_ORDER = {'warning': 0, 'notice': 1, 'info': 2}

# Flights in the same aircraft (or type) before its block speed means anything.
MIN_SPEED_SAMPLES = 3
# A plan this much faster than the pilot's usual block speed is optimistic.
FAST_PLAN = 1.2
# A leg this much longer than any logged, and by at least this many miles, is a step up.
LONG_LEG = 1.5
LONG_LEG_MIN_EXTRA_NM = 50
# The sun this far below the horizon ends civil twilight: dark, for planning purposes.
CIVIL_TWILIGHT = -6.0
# Current METARs say something about a flight leaving within this window.
WEATHER_WINDOW = (timedelta(hours=-1), timedelta(hours=3))


def sun_elevation(lat, lon, when):
    """The sun's elevation in degrees at a place and UTC time (to about a degree, plenty for twilight)."""
    days = when.timestamp() / 86400 - 10957.5  # since J2000.0
    mean_anomaly = math.radians(357.529 + 0.98560028 * days)
    mean_longitude = 280.459 + 0.98564736 * days
    longitude = math.radians(mean_longitude + 1.915 * math.sin(mean_anomaly) + 0.020 * math.sin(2 * mean_anomaly))
    obliquity = math.radians(23.439 - 0.00000036 * days)
    right_ascension = math.atan2(math.cos(obliquity) * math.sin(longitude), math.cos(longitude))
    declination = math.asin(math.sin(obliquity) * math.sin(longitude))
    sidereal_hours = (18.697374558 + 24.06570982441908 * days) % 24
    hour_angle = math.radians(sidereal_hours * 15 + lon) - right_ascension
    lat = math.radians(lat)
    return math.degrees(math.asin(
        math.sin(lat) * math.sin(declination) + math.cos(lat) * math.cos(declination) * math.cos(hour_angle)
    ))


def is_dark(airport, when):
    return sun_elevation(airport.lat, airport.lon, when) < CIVIL_TWILIGHT


def end_of_light(airport, when, step=timedelta(minutes=5), limit=timedelta(hours=18)):
    """The last moment before `when` that's still light at the airport, to the step, or None."""
    moment = when
    while when - moment <= limit:
        if not is_dark(airport, moment):
            return moment
        moment -= step
    return None


def _check(key, tone, title, detail, suggestion=''):
    return {'key': key, 'tone': tone, 'title': title, 'detail': detail, 'suggestion': suggestion}


def _zulu(moment):
    return f'{moment.astimezone(dt_timezone.utc):%H:%M}Z'


def _hm(hours):
    minutes = math.ceil(hours * 60)
    return f'{minutes // 60}:{minutes % 60:02d}'


def aircraft_checks(flight, aircraft, planned_hours):
    if not aircraft:
        return []
    reg = aircraft.registration
    if aircraft.grounded:
        return [_check(
            'grounded', 'warning', f'{reg} is grounded',
            'A flight reported it grounded and no maintenance has been logged since.',
            'Log the maintenance before this flight; until then AirFleet won’t accept it into the logbook.',
        )]
    found = []
    remaining = aircraft.maintenance_interval_hours - insights.hours(aircraft.hours_since_maintenance())
    if remaining < planned_hours:
        found.append(_check(
            'inspection', 'warning' if remaining <= 0 else 'notice',
            f'This flight takes {reg} past its {aircraft.maintenance_interval_hours}-hour inspection',
            f'{max(remaining, 0):.1f} h left on the inspection; this flight is {planned_hours:.1f} h.',
            'Get the inspection done first, or make sure the aircraft is legal to fly past it.',
        ))
    if aircraft.annual_due and aircraft.annual_due < flight.departure_time.date():
        found.append(_check(
            'annual', 'warning', f'{reg}’s annual runs out before this flight',
            f'The annual is due {aircraft.annual_due.isoformat()}.',
            'Have the annual done and log it before you go.',
        ))
    return found


def speed_check(flight, history, aircraft, distance, planned_hours):
    """Whether the planned block time matches how fast the pilot actually gets there in this aircraft."""
    if not distance or planned_hours <= 0:
        return None
    samples = history.filter(is_simulator=False, distance__gt=0)
    basis = samples.filter(registration_number=flight.registration_number)
    label = flight.registration_number
    totals = basis.aggregate(n=Count('id'), distance=Sum('distance'), time=Sum('total_time'))
    if totals['n'] < MIN_SPEED_SAMPLES and aircraft and aircraft.type_code:
        label = f'the {aircraft.type_code}'
        totals = samples.filter(aircraft__type_code=aircraft.type_code).aggregate(
            n=Count('id'), distance=Sum('distance'), time=Sum('total_time'),
        )
    if totals['n'] < MIN_SPEED_SAMPLES or not totals['time']:
        return None
    usual = totals['distance'] / (totals['time'].total_seconds() / 3600)
    planned = distance / planned_hours
    if planned <= usual * FAST_PLAN:
        return None
    needed = distance / usual
    landing = flight.departure_time + timedelta(hours=needed)
    return _check(
        'block_speed', 'notice', f'This plan is faster than you fly {label}',
        f'It assumes {round(planned)} kt block to block; your {totals["n"]} flights in {label} average {round(usual)} kt.',
        f'Budget about {_hm(needed)} block time, landing around {_zulu(landing)}, and plan fuel for it.',
    )


def long_leg_check(history, distance):
    real = history.filter(is_simulator=False)
    stats = real.aggregate(n=Count('id'), longest=Max('distance'))
    longest = stats['longest'] or 0
    if stats['n'] < MIN_SPEED_SAMPLES or not distance or distance < longest * LONG_LEG or distance - longest < LONG_LEG_MIN_EXTRA_NM:
        return None
    return _check(
        'long_leg', 'notice', 'Your longest leg yet',
        f'{distance:,} nm, against {longest:,} nm for the longest flight you’ve logged.',
        'Consider a fuel stop, and pick alternates along the way.',
    )


def new_airport_check(flight, history):
    if not history.exists() or flight.arrival_airport in insights.airports_visited(history):
        return None
    airport = airports.get(flight.arrival_airport)
    return _check(
        'new_airport', 'info', f'First time into {flight.arrival_airport}',
        airport.name if airport else 'You haven’t logged a flight to or from this airport.',
        'Look over the airport diagram, frequencies and pattern before you go, and pick an alternate you know.',
    )


def currency_checks(flight, history, now):
    """Passenger, night and instrument currency as it will stand on the day of the flight."""
    day = flight.departure_time.date()
    before = history.filter(departure_time__lt=flight.departure_time)
    current = {c['key']: c for c in insights.currency(before, today=day)}
    found = []

    arrival = airports.get(flight.arrival_airport)
    if arrival and is_dark(arrival, flight.arrival_time):
        light_ends = end_of_light(arrival, flight.arrival_time)
        twilight = f'Civil twilight ends at {_zulu(light_ends)} at {arrival.code}.' if light_ends else ''
        if current['passenger_night']['status'] == 'lapsed':
            leave_by = light_ends - flight.total_time if light_ends else None
            if leave_by and leave_by > now and leave_by.date() >= day - timedelta(days=1):
                suggestion = f'Leave by {_zulu(leave_by)} to land before dark, or fly it without passengers.'
            else:
                suggestion = 'Fly it without passengers, or with an instructor.'
            found.append(_check(
                'night_currency', 'warning', 'You’ll land after dark without night currency',
                f'Carrying passengers at night needs 3 full-stop night landings in the previous 90 days. {twilight}'.strip(),
                suggestion,
            ))
        else:
            found.append(_check('night', 'info', 'You’ll land after dark', twilight or 'The sun is down when you arrive.'))

    if current['passenger_day']['status'] == 'lapsed':
        found.append(_check(
            'passenger_currency', 'notice', 'You won’t be current to carry passengers',
            f'That needs 3 takeoffs and landings in the 90 days before the flight; you’ll have '
            f'{current["passenger_day"]["count_in_window"]}.',
            'Fly a few circuits first, or go without passengers.',
        ))
    instrument = current['instrument']
    if instrument['status'] == 'lapsed' and history.filter(approaches__gt=0).exists():
        found.append(_check(
            'instrument_currency', 'notice', f'You won’t be instrument current on {day.isoformat()}',
            f'That needs 6 approaches in the previous 6 calendar months; you’ll have {instrument["count_in_window"]}.',
            'If this is an IFR flight, get current first or plan it VFR.',
        ))
    return found


def weather_checks(flight, now):
    """Current conditions at either end, when the flight leaves soon enough for them to matter."""
    if not WEATHER_WINDOW[0] <= flight.departure_time - now <= WEATHER_WINDOW[1]:
        return []
    found = []
    for code in dict.fromkeys((flight.departure_airport, flight.arrival_airport)):
        try:
            report = external.metar(code)
        except external.ExternalLookupError:
            continue
        category = report.get('flight_category')
        if category in ('IFR', 'LIFR'):
            tone, title = 'warning', f'{code} is {category} right now'
        elif category == 'MVFR':
            tone, title = 'notice', f'{code} is marginal VFR right now'
        else:
            continue
        found.append(_check(
            f'weather_{code}', tone, title, report.get('raw', ''),
            'Get a full briefing with the forecast before deciding.',
        ))
    return found


def review(flight, history, aircraft, now=None):
    """Checks on a planned flight, most pressing first.

    history is the pilot's logged flights (drafts excluded); aircraft is their Aircraft for the
    flight's registration, or None.
    """
    if flight.is_simulator:
        return {'checks': [], 'simulator': True}
    now = now or datetime.now(dt_timezone.utc)
    planned_hours = flight.total_time.total_seconds() / 3600
    ends = airports.get(flight.departure_airport), airports.get(flight.arrival_airport)
    distance = flight.distance or (airports.distance_nm(*ends) if all(ends) else 0)

    checks = aircraft_checks(flight, aircraft, planned_hours)
    checks += [
        speed_check(flight, history, aircraft, distance, planned_hours),
        long_leg_check(history, distance),
        new_airport_check(flight, history),
    ]
    checks += currency_checks(flight, history, now) + weather_checks(flight, now)
    return {'checks': sorted((c for c in checks if c), key=lambda c: TONE_ORDER[c['tone']]), 'simulator': False}
