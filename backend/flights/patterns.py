"""Patterns across a pilot's flights, and recurring themes in their own notes.

findings() is plain arithmetic over the logbook: how recently and how much they fly, which skills have
gone unused, how concentrated their flying is and which aircraft are coming due. Each finding says what
the numbers are, so the pilot can check it.

note_themes() is the one part that needs a language model: it reads the free-text notes pilots write
after a flight ("floated the landing again", "crosswind was tough") and groups them into recurring
themes. It uses the quick log providers, and everything the model answers is checked here: a theme
can only cite flights it was shown, and it needs at least two of them.
"""
from collections import Counter
from datetime import date, timedelta

from django.db.models import Count, Q, Sum

from . import insights, quick_log

ZERO = timedelta(0)
TONE_ORDER = {'warning': 0, 'notice': 1, 'info': 2, 'good': 3}

# Days without flying before skills are worth refreshing.
RECENCY_NOTICE_DAYS = 30
RECENCY_WARNING_DAYS = 60
# How much the last 90 days must differ from the 90 before to call it a trend, and the least flying that counts.
TREND_CHANGE = 0.4
TREND_MIN_HOURS = 2
# One airport pair taking this share of a year's flights, once there are enough to tell.
CONCENTRATION_SHARE = 0.5
CONCENTRATION_MIN_FLIGHTS = 8
MAINTENANCE_HORIZON_DAYS = 30

MAX_THEME_NOTES = 40
MAX_NOTE_CHARS = 300
MIN_THEME_NOTES = 3
MAX_THEMES = 5
THEME_KINDS = ('struggle', 'strength', 'observation')

THEMES_PROMPT = """You read a pilot's own post-flight notes and find what keeps coming up across flights. Reply with one JSON object and nothing else:

{
  "themes": [
    {
      "title": a few words, e.g. "Crosswind landings",
      "kind": "struggle", "strength" or "observation",
      "summary": one sentence to the pilot, in the second person, about what the notes show,
      "flights": the numbers (#) of every flight whose note shows this theme
    }
  ]
}

Rules:
- Only report a theme that appears in the notes of at least two different flights. Use only what the notes say.
- At most five themes, the most frequent first. Prefer skills and recurring conditions over one-off events.
- Describe; don't instruct. You may suggest practising something with an instructor, but give no flying technique, procedures or regulatory advice.
- If nothing recurs, reply {"themes": []}."""


class ThemesError(Exception):
    """There isn't enough to read; the message is for the pilot."""


def _finding(key, tone, title, detail):
    return {'key': key, 'tone': tone, 'title': title, 'detail': detail}


def _plural(count, word):
    return f'{count} {word}{"" if count == 1 else "s"}'


def recency(flights, today):
    last = flights.filter(is_simulator=False).order_by('-departure_time').values_list('departure_time', flat=True).first()
    if not last:
        return None
    days = (today - last.date()).days
    if days >= RECENCY_WARNING_DAYS:
        tone = 'warning'
    elif days >= RECENCY_NOTICE_DAYS:
        tone = 'notice'
    else:
        return None
    return _finding(
        'recency', tone, f'{days} days since you last flew',
        'Landings and radio work fade first after a break. A few circuits, or a flight with an instructor, is a good way back in.',
    )


def trend(flights, today):
    recent_start, previous_start = today - timedelta(days=90), today - timedelta(days=180)
    totals = flights.aggregate(
        recent=Sum('total_time', filter=Q(departure_time__date__gt=recent_start, departure_time__date__lte=today)),
        previous=Sum('total_time', filter=Q(departure_time__date__gt=previous_start, departure_time__date__lte=recent_start)),
    )
    recent, previous = insights.hours(totals['recent']), insights.hours(totals['previous'])
    if max(recent, previous) < TREND_MIN_HOURS or previous == 0:
        return None
    change = (recent - previous) / previous
    if change <= -TREND_CHANGE:
        return _finding(
            'trend', 'notice', f'You’re flying {round(-change * 100)}% less',
            f'{recent} h in the last 90 days, down from {previous} h in the 90 before.',
        )
    if change >= TREND_CHANGE:
        return _finding(
            'trend', 'good', f'You’re flying {round(change * 100)}% more',
            f'{recent} h in the last 90 days, up from {previous} h in the 90 before.',
        )
    return None


def unused_skills(flights, today):
    """Night and instrument flying the pilot has done before but not lately. Currency covers the legal side."""
    year_ago, half_year_ago = today - timedelta(days=365), today - timedelta(days=182)
    real = flights.filter(is_simulator=False)
    night = Q(night_time__gt=ZERO) | Q(night_landings__gt=0)
    instrument = Q(instrument_time__gt=ZERO) | Q(simulated_instrument_time__gt=ZERO) | Q(approaches__gt=0)
    counts = flights.aggregate(
        night_ever=Count('id', filter=night & Q(is_simulator=False)),
        night_recent=Count('id', filter=night & Q(is_simulator=False, departure_time__date__gt=year_ago)),
        instrument_ever=Count('id', filter=instrument),
        instrument_recent=Count('id', filter=instrument & Q(departure_time__date__gt=half_year_ago)),
    )
    found = []
    if counts['night_ever'] and not counts['night_recent'] and real.filter(departure_time__date__gt=year_ago).exists():
        found.append(_finding(
            'night_unused', 'notice', 'No night flying in the past year',
            f'You’ve logged {_plural(counts["night_ever"], "night flight")}, but none in the last 12 months.',
        ))
    if counts['instrument_ever'] and not counts['instrument_recent'] and flights.filter(departure_time__date__gt=half_year_ago).exists():
        found.append(_finding(
            'instrument_unused', 'notice', 'No instrument work in six months',
            f'You’ve logged {_plural(counts["instrument_ever"], "flight")} with instrument time or approaches, '
            'but none in the last six months, simulator included.',
        ))
    return found


def concentration(flights, today):
    pairs = Counter(
        tuple(sorted(pair))
        for pair in flights.filter(departure_time__date__gt=today - timedelta(days=365))
        .values_list('departure_airport', 'arrival_airport')
    )
    total = sum(pairs.values())
    if total < CONCENTRATION_MIN_FLIGHTS:
        return None
    (first, second), count = pairs.most_common(1)[0]
    if count / total < CONCENTRATION_SHARE:
        return None
    route = first if first == second else f'{first}–{second}'
    return _finding(
        'concentration', 'info', f'Most of your flying is {route}',
        f'{count} of your {total} flights in the last 12 months. '
        'Unfamiliar airports, runways and airspace keep skills that a home route doesn’t use.',
    )


def new_airports(flights, today):
    year_ago = today - timedelta(days=365)
    before = insights.airports_visited(flights.filter(departure_time__date__lte=year_ago))
    since = insights.airports_visited(flights.filter(departure_time__date__gt=year_ago)) - before
    if not before or len(since) < 3:
        return None
    named = ', '.join(sorted(since)[:5]) + ('…' if len(since) > 5 else '')
    return _finding('new_airports', 'good', f'{len(since)} new airports this year', named)


def maintenance(fleet, today):
    """Aircraft grounded, or whose next inspection or annual falls in the next month at the current pace."""
    found = []
    for aircraft in fleet:
        if aircraft.grounded:
            found.append(_finding(
                f'maintenance_{aircraft.pk}', 'warning', f'{aircraft.registration} is grounded',
                'Log its maintenance before its next flight.',
            ))
            continue
        forecast = insights.maintenance_forecast(
            insights.hours(aircraft.hours_since_maintenance()), aircraft.maintenance_interval_hours,
            insights.hours(aircraft.recent_time), aircraft.annual_due, today,
        )
        due = forecast['next_due']
        if not due:
            continue
        days = (date.fromisoformat(due['date']) - today).days
        if days > MAINTENANCE_HORIZON_DAYS:
            continue
        what = 'annual' if due['kind'] == 'annual' else f'{aircraft.maintenance_interval_hours}-hour inspection'
        if days <= 0:
            title, tone = f'{aircraft.registration}’s {what} is due', 'warning'
        else:
            title, tone = f'{aircraft.registration}’s {what} is due in about {_plural(days, "day")}', 'notice'
        detail = (
            f'{forecast["hours_remaining"]} h left on the inspection at {forecast["hours_per_week"]} h a week.'
            if due['kind'] == 'inspection' else f'The annual is due {due["date"]}.'
        )
        found.append(_finding(f'maintenance_{aircraft.pk}', tone, title, detail))
    return found


def findings(flights, fleet, today):
    """What stands out in the pilot's logged flights and fleet, most pressing first.

    flights must already exclude drafts; fleet is the annotated queryset from views.fleet().
    """
    found = [recency(flights, today), trend(flights, today), concentration(flights, today), new_airports(flights, today)]
    found += unused_skills(flights, today) + maintenance(fleet, today)
    return sorted((f for f in found if f), key=lambda f: TONE_ORDER[f['tone']])


def _flight_ref(flight):
    return {
        'id': flight.id,
        'date': flight.departure_time.date().isoformat(),
        'route': f'{flight.departure_airport} → {flight.arrival_airport}',
    }


def build_theme_messages(flights):
    lines = [
        f'#{f.id} {f.departure_time:%Y-%m-%d} {f.departure_airport}-{f.arrival_airport}: '
        + ' '.join(f.notes.split())[:MAX_NOTE_CHARS]
        for f in flights
    ]
    user = "The pilot's notes, newest first:\n<<<\n" + '\n'.join(lines) + '\n>>>'
    return [{'role': 'system', 'content': THEMES_PROMPT}, {'role': 'user', 'content': user}]


def clean_themes(data, flights):
    """The model's themes, keeping only well-formed ones that cite at least two of the flights it was shown."""
    by_id = {f.id: f for f in flights}
    themes = data.get('themes') if isinstance(data, dict) else None
    result = []
    for theme in themes if isinstance(themes, list) else []:
        if not isinstance(theme, dict):
            continue
        title, summary, kind = theme.get('title'), theme.get('summary'), theme.get('kind')
        if not (isinstance(title, str) and title.strip() and isinstance(summary, str) and summary.strip()):
            continue
        cited = []
        for value in theme.get('flights') if isinstance(theme.get('flights'), list) else []:
            try:
                flight_id = int(str(value).lstrip('#'))
            except ValueError:
                continue
            if flight_id in by_id and flight_id not in cited:
                cited.append(flight_id)
        if len(cited) < 2:
            continue
        result.append({
            'title': title.strip()[:60],
            'kind': kind if kind in THEME_KINDS else 'observation',
            'summary': summary.strip()[:300],
            'flights': [_flight_ref(by_id[i]) for i in cited],
        })
        if len(result) == MAX_THEMES:
            break
    return result


def note_themes(flights):
    """Recurring themes in the notes of the pilot's most recent logged flights."""
    noted = list(flights.exclude(notes='').order_by('-departure_time')[:MAX_THEME_NOTES])
    if len(noted) < MIN_THEME_NOTES:
        raise ThemesError(f'Write notes on at least {MIN_THEME_NOTES} flights and themes will show up here.')
    if not quick_log.enabled():
        raise quick_log.QuickLogUnavailable
    themes = clean_themes(quick_log.complete(build_theme_messages(noted)), noted)
    return {'themes': themes, 'notes_read': len(noted)}
