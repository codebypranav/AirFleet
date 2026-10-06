"""CSV export and import: AirFleet's own format and ForeFlight logbook exports."""
import csv
import io
from datetime import datetime, time, timedelta, timezone as dt_timezone

from .models import Aircraft, Flight
from .serializers import FlightSerializer

EXPORT_FIELDS = [
    'departure_airport', 'arrival_airport', 'departure_time', 'arrival_time', 'total_time',
    'registration_number', 'aircraft_type', 'aircraft_condition', 'distance',
    'pic_time', 'sic_time', 'dual_received_time', 'night_time', 'instrument_time', 'simulated_instrument_time',
    'day_landings', 'night_landings', 'approaches', 'cross_country', 'is_simulator',
    'departure_gate', 'arrival_gate', 'flight_plan', 'weather_conditions', 'notes',
    'instructor_name', 'instructor_certificate', 'instructor_signed_at', 'signature_status',
]
# From the flight's latest instructor signature. Informational: a signature can't be imported.
SIGNATURE_FIELDS = {
    'instructor_name': 'instructor_name',
    'instructor_certificate': 'certificate_number',
    'instructor_signed_at': 'signed_at',
    'signature_status': 'status',
}
# Read back on import; aircraft_type and the signature columns are informational only.
IMPORT_FIELDS = [f for f in EXPORT_FIELDS if f not in ('aircraft_type', *SIGNATURE_FIELDS)]

FOREFLIGHT_CLASSES = {
    'airplane_single_engine_land': 'SEL',
    'airplane_multi_engine_land': 'MEL',
    'airplane_single_engine_sea': 'SES',
    'airplane_multi_engine_sea': 'MES',
    'rotorcraft_helicopter': 'HELICOPTER',
    'glider': 'GLIDER',
}


def export_csv(flights):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=EXPORT_FIELDS, extrasaction='ignore')
    writer.writeheader()
    for flight in flights.select_related('aircraft').prefetch_related('signatures'):
        row = FlightSerializer(flight).data
        signature = row.get('signature') or {}
        row.update({column: signature.get(key, '') for column, key in SIGNATURE_FIELDS.items()})
        writer.writerow({field: row.get(field, '') for field in EXPORT_FIELDS})
    return out.getvalue()


class LogbookImportError(Exception):
    pass


def _hours(value):
    try:
        return timedelta(hours=float(value)) if value not in (None, '') else timedelta(0)
    except ValueError:
        return timedelta(0)


def _int(value):
    try:
        return int(float(value)) if value not in (None, '') else 0
    except ValueError:
        return 0


def _clock(value):
    """ForeFlight clock times are UTC and look like 1435 or 14:35."""
    digits = (value or '').replace(':', '').strip()
    if len(digits) in (3, 4) and digits.isdigit():
        digits = digits.zfill(4)
        return time(int(digits[:2]) % 24, int(digits[2:]) % 60)
    return None


def _tables(text):
    """Split a ForeFlight export into its named tables ("Aircraft Table", "Flights Table")."""
    tables, name, rows = {}, None, []
    for row in csv.reader(io.StringIO(text)):
        first = row[0].strip() if row else ''
        if first.endswith(' Table'):
            if name:
                tables[name] = rows
            name, rows = first, []
        elif name is not None:
            rows.append(row)
    if name:
        tables[name] = rows
    parsed = {}
    for name, rows in tables.items():
        rows = [r for r in rows if any(cell.strip() for cell in r)]
        if not rows:
            continue
        header = [h.strip() for h in rows[0]]
        parsed[name] = [dict(zip(header, r)) for r in rows[1:]]
    return parsed


def _approach_count(row):
    total = 0
    for i in range(1, 7):
        value = (row.get(f'Approach{i}') or '').strip()
        if value:
            first = value.split(';')[0]
            total += int(first) if first.isdigit() else 1
    return total


def parse_foreflight(text):
    tables = _tables(text)
    if 'Flights Table' not in tables:
        raise LogbookImportError("This doesn't look like a ForeFlight logbook export (no Flights Table found).")

    aircraft = {}
    for row in tables.get('Aircraft Table', []):
        reg = (row.get('AircraftID') or '').strip().upper()
        if reg:
            aircraft[reg] = {
                'type_code': (row.get('TypeCode') or '').strip().upper()[:4],
                'make_model': ' '.join(filter(None, [(row.get('Make') or '').strip(), (row.get('Model') or '').strip()]))[:60],
                'aircraft_class': FOREFLIGHT_CLASSES.get((row.get('Class') or '').strip().lower(), 'OTHER'),
            }

    flights = []
    for row in tables['Flights Table']:
        total = _hours(row.get('TotalTime'))
        if not row.get('Date') or total <= timedelta(0):
            flights.append({'_error': 'Missing date or total time', '_raw': row})
            continue
        try:
            day = datetime.strptime(row['Date'].strip(), '%Y-%m-%d').date()
        except ValueError:
            flights.append({'_error': f"Unrecognised date {row['Date']!r}", '_raw': row})
            continue
        start = _clock(row.get('TimeOff')) or _clock(row.get('TimeOut')) or time(12, 0)
        departure = datetime.combine(day, start, tzinfo=dt_timezone.utc)
        night_landings = _int(row.get('NightLandingsFullStop'))
        all_landings = _int(row.get('AllLandings'))
        flights.append({
            'departure_airport': (row.get('From') or '').strip().upper(),
            'arrival_airport': (row.get('To') or row.get('From') or '').strip().upper(),
            'departure_time': departure,
            'arrival_time': departure + total,
            'total_time': total,
            'registration_number': (row.get('AircraftID') or '').strip().upper() or 'UNKNOWN',
            'distance': _int(row.get('Distance')),
            'pic_time': min(_hours(row.get('PIC')), total),
            'sic_time': min(_hours(row.get('SIC')), total),
            'dual_received_time': min(_hours(row.get('DualReceived')), total),
            'night_time': min(_hours(row.get('Night')), total),
            'instrument_time': min(_hours(row.get('ActualInstrument')), total),
            'simulated_instrument_time': min(_hours(row.get('SimulatedInstrument')), total),
            'day_landings': max(all_landings - night_landings, _int(row.get('DayLandingsFullStop'))),
            'night_landings': night_landings,
            'approaches': _approach_count(row),
            'cross_country': _hours(row.get('CrossCountry')) > timedelta(0),
            'is_simulator': _hours(row.get('SimulatedFlight')) > timedelta(0),
            'flight_plan': (row.get('Route') or '').strip(),
            'notes': (row.get('PilotComments') or '').strip(),
        })
    return flights, aircraft


def parse_airfleet(text):
    reader = csv.DictReader(io.StringIO(text))
    missing = {'departure_airport', 'arrival_airport', 'departure_time', 'arrival_time', 'registration_number'} - set(reader.fieldnames or [])
    if missing:
        raise LogbookImportError(f"Missing columns: {', '.join(sorted(missing))}. Export a CSV from AirFleet to see the format.")
    rows = []
    for row in reader:
        rows.append({k: v for k, v in row.items() if k in IMPORT_FIELDS and v not in (None, '')})
    return rows, {}


def detect_and_parse(text):
    head = text[:4000]
    first_line = head.splitlines()[0] if head else ''
    if 'Flights Table' in head or 'ForeFlight' in first_line:
        return 'foreflight', *parse_foreflight(text)
    return 'airfleet', *parse_airfleet(text)


def import_flights(text, request):
    """Create every valid row, skipping duplicates. Returns a summary with per-row problems."""
    source, rows, aircraft_info = detect_and_parse(text)
    user = request.user
    existing = set(Flight.objects.filter(user=user).values_list('departure_time', 'departure_airport', 'arrival_airport'))

    created, duplicates, errors = 0, 0, []
    for line, row in enumerate(rows, start=1):
        if '_error' in row:
            errors.append({'row': line, 'errors': row['_error']})
            continue
        serializer = FlightSerializer(data=row, context={'request': request, 'historical': True})
        if not serializer.is_valid():
            errors.append({'row': line, 'errors': serializer.errors})
            continue
        data = serializer.validated_data
        key = (data['departure_time'], data['departure_airport'], data['arrival_airport'])
        if key in existing:
            duplicates += 1
            continue
        serializer.save(user=user)
        existing.add(key)
        created += 1

    for reg, info in aircraft_info.items():
        plane = Aircraft.objects.filter(user=user, registration=reg).first()
        if plane:
            # Fill in what the pilot hasn't set; SEL is the model default, so treat it as unset.
            changed = {k: v for k, v in info.items() if k != 'aircraft_class' and v and not getattr(plane, k)}
            if plane.aircraft_class == 'SEL' and info['aircraft_class'] not in ('SEL', 'OTHER'):
                changed['aircraft_class'] = info['aircraft_class']
            for k, v in changed.items():
                setattr(plane, k, v)
            if changed:
                plane.save()

    return {'source': source, 'created': created, 'duplicates': duplicates, 'skipped': len(errors), 'errors': errors[:50]}
