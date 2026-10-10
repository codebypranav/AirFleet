"""Sanity limits that keep impossible flights out of the logbook.

Entries like a transatlantic hop in twenty minutes or a flight dated 2062 are
almost always a typo, and they quietly poison every total, currency window and
ranking they land in. The bounds here come from the physical flight envelope
rather than from the fleet that happens to be flying today, so they are
deliberately roomy: a new Concorde, or anything else modern technology makes
possible, still logs without an argument.
"""
from datetime import date, timedelta

# Mach ~3.4 in the cruise, past the SR-71. Concorde's New York block speed was
# around 1,050 kt, so supersonic airliners have plenty of room.
MAX_BLOCK_SPEED_KT = 2000
# Longer than any crewed non-stop flight an airline or a GA pilot plans.
MAX_FLIGHT_HOURS = 48
# A planned flight further out than this is a mistyped year, not a plan.
MAX_PLAN_AHEAD_YEARS = 2
# A tight visual circuit takes about three minutes; an instrument approach five.
MAX_LANDINGS_PER_HOUR = 20
MAX_APPROACHES_PER_HOUR = 12
# Nothing was logged before the Wright brothers.
FIRST_POWERED_FLIGHT = date(1903, 12, 17)
# A device clock running a little ahead shouldn't block a flight just landed.
CLOCK_SKEW = timedelta(hours=1)
# Great-circle distances are whole miles and routes bend, but a logged distance
# this far below the great circle is a typo.
DISTANCE_TOLERANCE = 0.9


def hours(duration):
    return duration.total_seconds() / 3600 if duration else 0.0


def allowance(flight_hours, per_hour):
    """How many landings or approaches fit in the flight. Even a short hop gets one."""
    return max(1, int(flight_hours * per_hour))


def problems(*, departure_time, arrival_time, total_time, now, distance=0, great_circle=None,
             day_landings=0, night_landings=0, approaches=0, is_draft=False, is_simulator=False):
    """Field name -> what couldn't have happened, for everything out of the envelope.

    ``great_circle`` is only passed when the pilot supplied the distance themselves;
    a distance AirFleet worked out from the airports is the great circle already.
    """
    found = {}
    block_hours = hours(total_time)

    if departure_time.date() < FIRST_POWERED_FLIGHT:
        found['departure_time'] = (
            f"Powered flight started on {FIRST_POWERED_FLIGHT:%d %B %Y}, so this date can't be right. "
            "Check the year."
        )
    elif is_draft and departure_time > now + timedelta(days=365 * MAX_PLAN_AHEAD_YEARS):
        found['departure_time'] = (
            f"A planned flight more than {MAX_PLAN_AHEAD_YEARS} years out is usually a mistyped year. "
            "Check the date."
        )

    if not is_draft and arrival_time > now + CLOCK_SKEW:
        found['arrival_time'] = "This flight hasn't happened yet. Check the date, or save it as a planned flight."

    if block_hours > MAX_FLIGHT_HOURS:
        found['total_time'] = (
            f"{block_hours:.1f} hours is longer than a single flight lasts; AirFleet takes up to "
            f"{MAX_FLIGHT_HOURS} hours. Check the dates."
        )

    # A simulator can be repositioned mid-session, so its distance says nothing about its speed.
    if not is_simulator and distance and block_hours:
        speed = distance / block_hours
        if speed > MAX_BLOCK_SPEED_KT:
            found['distance'] = (
                f"{distance:,} nm in {block_hours:.1f} hours works out to {round(speed):,} kt, faster than "
                "any aircraft flies. Check the times and the distance."
            )
    if great_circle and distance and distance < great_circle * DISTANCE_TOLERANCE:
        found['distance'] = (
            f"These airports are {great_circle:,} nm apart, so a {distance:,} nm flight between them "
            "isn't possible. Check the distance."
        )

    landings = (day_landings or 0) + (night_landings or 0)
    if landings > allowance(block_hours, MAX_LANDINGS_PER_HOUR):
        field = 'night_landings' if (night_landings or 0) > (day_landings or 0) else 'day_landings'
        found[field] = (
            f"{landings} landings leave no time to fly the circuits in {block_hours:.1f} hours. "
            "Check the count and the times."
        )
    if (approaches or 0) > allowance(block_hours, MAX_APPROACHES_PER_HOUR):
        found['approaches'] = (
            f"{approaches} approaches don't fit in {block_hours:.1f} hours. Check the count and the times."
        )
    return found
