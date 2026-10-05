"""Read a flight plan PDF (a SimBrief OFP or any plan with an ICAO flight plan) into a draft logbook entry.

Every format is anchored on the ICAO ATC flight plan, "(FPL-...)", which airline and SimBrief OFPs both
print: it gives the callsign, aircraft type, airports, off-block time, route, date (DOF/) and
registration (REG/). The OFP's OUT/OFF/ON/IN times table, when there is one, gives the block times.
"""
import io
import re
from datetime import datetime, timedelta, timezone as dt_timezone

from pypdf import PdfReader

# OFPs put the plan up front; anything after this is weather, NOTAMs and charts.
MAX_PAGES = 30
MONTHS = {m: i for i, m in enumerate(('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'), 1)}

FPL_RE = re.compile(r'\(FPL-(.*?)\)', re.S)
SPEED_LEVEL_RE = re.compile(r'^[NKM]\d{3,4}(?:[FAS]\d{3,4}|M\d{4}|VFR)$')
# A clock time in a times table: 1655 or 1655Z, but not a local time like 1855L.
CLOCK_RE = re.compile(r'(?<![\d/.])([01]\d|2[0-3])([0-5]\d)Z?(?![\dL])')
TIMES_ROW_RE = re.compile(r'^\s*(OUT|OFF|ON|IN)\b(.*)$', re.M)
SCHEDULED_HEADERS = ('SKED', 'SCHED', 'SCHEDULED', 'STD')
TIMES_HEADERS = ('ESTIMATED', 'EST', 'PLAN', 'PLANNED', 'ACTUAL', 'ACT') + SCHEDULED_HEADERS
DISTANCE_RE = re.compile(r'\b(?:GND|GROUND)\s+DIST(?:ANCE)?\s+(\d{2,5})\b')
HEADER_DATE_RE = re.compile(r'\b(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{4}|\d{2})\b')


class FlightPlanError(Exception):
    pass


def extract_text(data):
    """The text of the first pages of a PDF, laid out as printed (OFPs are monospaced)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt('')
        pages = [page.extract_text(extraction_mode='layout') or '' for page in reader.pages[:MAX_PAGES]]
    except Exception as e:  # noqa: BLE001 - uploaded files are untrusted; pypdf raises many types on bad input
        raise FlightPlanError("That file couldn't be read as a PDF.") from e
    text = '\n'.join(pages)
    if not text.strip():
        raise FlightPlanError('This PDF has no text in it. Scanned or photographed plans aren’t supported yet.')
    return text


def parse_icao_fpl(text):
    """The fields of the first ICAO flight plan message in the text, or None."""
    match = FPL_RE.search(text)
    if not match:
        return None
    # Items start on a new "-"; join the lines first so wrapped items read as one.
    items = [item.strip() for item in re.split(r'\s+-(?=\S)', ' '.join(match.group(1).split()))]
    fpl = {'callsign': items[0].split('-')[0]}

    for item in items[1:]:
        # Items 9 and 10: [number]type/wake-equipment, e.g. A21N/M-SDE3FGHIJ1/LB1 or 2F16/M-S/C.
        if 'aircraft_type' not in fpl and (m := re.fullmatch(r'\d?([A-Z][A-Z0-9]{1,3})/[LMHJ]', item.split('-')[0])):
            fpl['aircraft_type'] = m.group(1)
        # Item 13: departure and off-block time, e.g. LFBO1655.
        elif 'departure' not in fpl and (m := re.fullmatch(r'([A-Z]{4})(\d{4})', item)):
            fpl['departure'], fpl['eobt'] = m.group(1), m.group(2)
        # Item 15: cruise speed and level, then the route.
        elif 'departure' in fpl and 'route' not in fpl and SPEED_LEVEL_RE.match(item.split()[0]):
            route = [token.split('/')[0] for token in item.split()[1:]]
            fpl['route'] = ' '.join(route)
        # Item 16: destination, total EET and alternates, e.g. CYUL0748 CYOW.
        elif 'route' in fpl and 'destination' not in fpl and (m := re.fullmatch(r'([A-Z]{4})(\d{4})((?:\s+[A-Z]{4})*)', item)):
            fpl['destination'], fpl['eet'] = m.group(1), m.group(2)
            fpl['alternates'] = m.group(3).split()
        # Item 18: other information.
        elif 'destination' in fpl:
            if m := re.search(r'\bDOF/(\d{6})\b', item):
                fpl['dof'] = m.group(1)
            if m := re.search(r'\bREG/([A-Z0-9]+)\b', item):
                fpl['reg'] = m.group(1)
    return fpl


def _date_of_flight(text, fpl):
    if fpl and fpl.get('dof'):
        try:
            return datetime.strptime(fpl['dof'], '%y%m%d').date()
        except ValueError:
            pass
    if m := HEADER_DATE_RE.search(text):
        day, month, year = m.groups()
        year = int(year) + (2000 if len(year) == 2 else 0)
        try:
            return datetime(year, MONTHS[month], int(day)).date()
        except ValueError:
            pass
    return None


def parse_times_table(text):
    """{'OUT': '1655', 'IN': '0125', ...} from the OFP times table, taking the scheduled column if labelled."""
    lines = text.splitlines()
    rows = {}
    for match in TIMES_ROW_RE.finditer(text):
        label = match.group(1)
        clocks = [h + m for h, m in CLOCK_RE.findall(match.group(2))]
        if label in rows or not clocks:
            continue
        # Look a few lines up for the column headings (ESTIMATED SKED ACTUAL).
        line_no = text.count('\n', 0, match.start())
        column = 0
        for above in reversed(lines[max(0, line_no - 6):line_no]):
            headers = [word for word in above.split() if word in TIMES_HEADERS]
            if len(headers) >= 2:
                filled = [h for h in headers if h not in ('ACTUAL', 'ACT')]
                column = next((i for i, h in enumerate(filled) if h in SCHEDULED_HEADERS), 0)
                break
        rows[label] = clocks[min(column, len(clocks) - 1)]
    return rows


def _at(day, clock):
    return datetime(day.year, day.month, day.day, int(clock[:2]), int(clock[2:]), tzinfo=dt_timezone.utc)


def _block_times(day, eobt, times):
    """Departure and arrival datetimes. Each time after the first rolls into the next day if it reads earlier."""
    out_clock = times.get('OUT') or eobt
    if not (day and out_clock):
        return None, None
    current = _at(day, out_clock)
    departure = current
    for label in ('OFF', 'ON', 'IN'):
        if clock := times.get(label):
            moment = _at(current.date(), clock)
            if moment < current:
                moment += timedelta(days=1)
            current = moment
    return departure, (current if 'IN' in times else None)


def _registration(text, reg):
    """REG/ drops the dash (CGXLR); use the dashed form if the OFP prints one (C-GXLR)."""
    if not reg:
        return ''
    pattern = r'\b' + r'-?'.join(map(re.escape, reg)) + r'\b'
    for m in re.finditer(pattern, text):
        if '-' in m.group(0):
            return m.group(0)
    return reg


def detect_source(text):
    upper = text.upper()
    if 'SIMBRIEF' in upper or 'NOT FOR REAL WORLD NAVIGATION' in upper:
        return 'simbrief'
    return 'icao'


def parse(text):
    """A draft flight (the keys FlightSerializer takes) plus source, callsign and warnings."""
    source = detect_source(text)
    fpl = parse_icao_fpl(text)
    if not fpl or 'departure' not in fpl or 'destination' not in fpl:
        raise FlightPlanError(
            "Couldn't find the ATC flight plan, (FPL-...), in this PDF. "
            "Upload a SimBrief OFP or a plan that includes the ICAO flight plan page."
        )

    warnings = []
    day = _date_of_flight(text, fpl)
    times = parse_times_table(text)
    departure, arrival = _block_times(day, fpl.get('eobt'), times)
    if departure and not arrival and fpl.get('eet'):
        # No times table: off-block plus the en-route estimate, which leaves out taxi time.
        arrival = departure + timedelta(hours=int(fpl['eet'][:2]), minutes=int(fpl['eet'][2:]))
        warnings.append('No block times in the plan, so arrival is off-block plus the en-route time. Add taxi time.')
    if not day:
        warnings.append("Couldn't find the date of the flight. Fill in the times.")

    distance = DISTANCE_RE.search(text)
    notes = [f"Flight plan: {fpl['callsign']}"]
    if fpl.get('alternates'):
        notes.append(f"Alternate: {', '.join(fpl['alternates'])}")

    draft = {
        'departure_airport': fpl['departure'],
        'arrival_airport': fpl['destination'],
        'departure_time': departure.isoformat() if departure else None,
        'arrival_time': arrival.isoformat() if arrival else None,
        'registration_number': _registration(text, fpl.get('reg'))[:10],
        'aircraft_type': fpl.get('aircraft_type', ''),
        'flight_plan': fpl.get('route', ''),
        'distance': int(distance.group(1)) if distance else 0,
        'is_simulator': source == 'simbrief',
        'notes': '. '.join(notes),
    }
    if not draft['registration_number']:
        warnings.append('No registration in the plan. Add the aircraft before saving.')
    return {'source': source, 'callsign': fpl['callsign'], 'flight': draft, 'warnings': warnings}


def read(data):
    return parse(extract_text(data))
