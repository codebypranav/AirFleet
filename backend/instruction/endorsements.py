"""Kinds of endorsement, each with a starting draft and how long it lasts.

The drafts are plain-language starting points for the common US endorsements (the topics of
AC 61-65), not the AC's wording. The instructor edits the text before signing and is responsible
for it.
"""
import calendar
from datetime import date, timedelta

# validity: ('days', n) counts from the day given; ('calendar_months', n) runs to the end of the
# nth month after it, the way the FAA counts calendar months.
KINDS = {
    'pre_solo_knowledge': {
        'title': 'Pre-solo knowledge test',
        'regulation': '14 CFR 61.87(b)',
        'draft': "I certify that {student} has satisfactorily completed the pre-solo knowledge test of "
                 "§ 61.87(b) for the {aircraft}.",
        'needs_aircraft': True,
    },
    'pre_solo_flight': {
        'title': 'Pre-solo flight training',
        'regulation': '14 CFR 61.87(c)',
        'draft': "I certify that {student} has received and logged pre-solo flight training in the maneuvers "
                 "and procedures appropriate to the {aircraft}, and has demonstrated satisfactory proficiency "
                 "and safety in them.",
        'needs_aircraft': True,
    },
    'solo': {
        'title': 'Solo flight',
        'regulation': '14 CFR 61.87(n)',
        'draft': "I certify that {student} has received the training required to fly solo, meets the "
                 "requirements of § 61.87(n), and is proficient to make solo flights in the {aircraft}.",
        'needs_aircraft': True,
        'validity': ('days', 90),
    },
    'solo_cross_country': {
        'title': 'Solo cross-country',
        'regulation': '14 CFR 61.93(c)',
        'draft': "I certify that {student} has received the required solo cross-country training, meets the "
                 "requirements of § 61.93, and is proficient to make solo cross-country flights in the {aircraft}.",
        'needs_aircraft': True,
    },
    'knowledge_test': {
        'title': 'Knowledge test',
        'regulation': '14 CFR 61.35(a)(1)',
        'draft': "I certify that {student} has received the required training and I have determined they are "
                 "prepared for the private pilot knowledge test.",
    },
    'practical_test': {
        'title': 'Practical test (checkride)',
        'regulation': '14 CFR 61.39(a)(6)',
        'draft': "I certify that {student} has received the required training, is prepared for the private pilot "
                 "practical test, and has received training in the areas of deficiency on their knowledge test report.",
        'validity': ('calendar_months', 2),
    },
    'flight_review': {
        'title': 'Flight review',
        'regulation': '14 CFR 61.56',
        'draft': "{student} has satisfactorily completed a flight review under § 61.56.",
        'validity': ('calendar_months', 24),
    },
    'ipc': {
        'title': 'Instrument proficiency check',
        'regulation': '14 CFR 61.57(d)',
        'draft': "{student} has satisfactorily completed the instrument proficiency check of § 61.57(d) in the {aircraft}.",
        'needs_aircraft': True,
    },
    'complex': {
        'title': 'Complex airplane',
        'regulation': '14 CFR 61.31(e)',
        'draft': "I certify that {student} has received the required ground and flight training in a complex "
                 "airplane and is proficient in its operation and systems.",
    },
    'high_performance': {
        'title': 'High-performance airplane',
        'regulation': '14 CFR 61.31(f)',
        'draft': "I certify that {student} has received the required ground and flight training in a "
                 "high-performance airplane and is proficient in its operation and systems.",
    },
    'tailwheel': {
        'title': 'Tailwheel airplane',
        'regulation': '14 CFR 61.31(i)',
        'draft': "I certify that {student} has received the required training in a tailwheel airplane and is "
                 "proficient in normal and crosswind takeoffs and landings, wheel landings and go-arounds.",
    },
    'other': {
        'title': '',
        'regulation': '',
        'draft': '',
    },
}


def add_calendar_months(day, months):
    """The last day of the month `months` after `day`'s month."""
    month_index = day.month - 1 + months
    year, month = day.year + month_index // 12, month_index % 12 + 1
    return date(year, month, calendar.monthrange(year, month)[1])


def expiry(kind, given_on):
    validity = KINDS[kind].get('validity')
    if not validity:
        return None
    unit, n = validity
    return given_on + timedelta(days=n) if unit == 'days' else add_calendar_months(given_on, n)


def catalogue():
    return [
        {
            'kind': kind,
            'title': info['title'],
            'regulation': info['regulation'],
            'draft': info['draft'],
            'needs_aircraft': info.get('needs_aircraft', False),
            'validity': info.get('validity'),
        }
        for kind, info in KINDS.items()
    ]
