from datetime import timedelta

from django.utils import timezone

from flights.insights import hours
from . import endorsements
from .endorsements import add_calendar_months
from .serializers import latest_signature

ZERO = timedelta(0)


def solo(f):
    return f.dual_received_time == ZERO


HOURS = (
    ('total', 'Total flight time', '61.109(a)', 40, 'h', lambda f, since: f.total_time),
    ('dual', 'Dual received', '61.109(a)', 20, 'h', lambda f, since: f.dual_received_time),
    ('dual_xc', 'Dual cross-country', '61.109(a)(1)', 3, 'h',
     lambda f, since: f.dual_received_time if f.cross_country else ZERO),
    ('dual_night', 'Dual night', '61.109(a)(2)', 3, 'h', lambda f, since: min(f.night_time, f.dual_received_time)),
    ('night_landings', 'Night takeoffs and landings with an instructor', '61.109(a)(2)(ii)', 10, '',
     lambda f, since: 0 if solo(f) else f.night_landings),
    ('dual_instrument', 'Dual simulated instrument', '61.109(a)(3)', 3, 'h',
     lambda f, since: min(f.simulated_instrument_time, f.dual_received_time)),
    ('dual_recent', 'Dual in the last 2 calendar months (test prep)', '61.109(a)(4)', 3, 'h',
     lambda f, since: f.dual_received_time if since <= timezone.localdate(f.departure_time) <= timezone.localdate() else ZERO),
    ('solo', 'PIC without dual (counted as solo)', '61.109(a)(5)', 10, 'h',
     lambda f, since: f.pic_time if solo(f) else ZERO),
    ('solo_xc', 'Solo cross-country', '61.109(a)(5)(i)', 5, 'h',
     lambda f, since: f.pic_time if solo(f) and f.cross_country else ZERO),
)

CHECKS = [
    {'label': 'Night cross-country over 100 nm total distance', 'regulation': '61.109(a)(2)(i)'},
    {'label': 'Solo cross-country of 150 nm, full-stop landings at three points, one leg over 50 nm',
     'regulation': '61.109(a)(5)(ii)'},
    {'label': 'Three solo full-stop takeoffs and landings at a towered airport', 'regulation': '61.109(a)(5)(iii)'},
]

ENDORSEMENTS = ('pre_solo_knowledge', 'pre_solo_flight', 'solo', 'solo_cross_country', 'knowledge_test', 'practical_test')


def progress(flights, received, today):
    since = add_calendar_months(today, -3) + timedelta(days=1)
    rows, missing = [], []
    for key, label, regulation, need, unit, credit in HOURS:
        total = sum((credit(f, since) for f in flights), ZERO if unit else 0)
        have = hours(total) if unit else total
        exact = total.total_seconds() / 3600 if unit else total
        short = max(round(need - exact, 1), 0.1) if exact < need else 0
        row = {'key': key, 'label': label, 'regulation': regulation, 'unit': unit, 'have': have, 'need': need, 'short': short}
        if key == 'dual':
            row['signed'] = hours(sum(
                (f.dual_received_time for f in flights if (s := latest_signature(f)) and s.holds(f)), ZERO,
            ))
        rows.append(row)
        if short:
            missing.append(f"{label}: {short}{' ' + unit if unit else ''} to go")

    standing = [_standing(kind, received, today) for kind in ENDORSEMENTS]
    for e in standing:
        if e['status'] == 'expired':
            missing.append(f"{e['title']} endorsement expired {e['expires_on']:%Y-%m-%d}")
        elif e['status'] == 'missing':
            missing.append(f"{e['title']} endorsement missing")
    return {'hours': rows, 'endorsements': standing, 'missing': missing}


def _standing(kind, received, today):
    live = [e for e in received if e.kind == kind and not e.withdrawn_at]
    best = max(live, key=lambda e: (e.status(today) == 'current', e.expires_on or e.given_on), default=None)
    info = endorsements.KINDS[kind]
    return {
        'kind': kind, 'title': info['title'], 'regulation': info['regulation'],
        'status': best.status(today) if best else 'missing', 'expires_on': best.expires_on if best else None,
    }
