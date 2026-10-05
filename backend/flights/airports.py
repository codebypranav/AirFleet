"""Airport lookups backed by a bundled extract of OurAirports (public domain).

data/airports.csv.gz holds every open airport and seaplane base with a
4-character ICAO-style code. Regenerate it from
https://davidmegginson.github.io/ourairports-data/airports.csv when needed.
"""
import csv
import gzip
import math
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / 'data' / 'airports.csv.gz'
EARTH_RADIUS_NM = 3440.065
SIZE_RANK = {'large': 0, 'medium': 1, 'small': 2, 'seaplane': 3}


@dataclass(frozen=True)
class Airport:
    code: str
    name: str
    city: str
    country: str
    lat: float
    lon: float
    size: str

    def as_dict(self):
        return asdict(self)


@lru_cache(maxsize=1)
def _airports():
    with gzip.open(DATA_FILE, 'rt', newline='', encoding='utf-8') as f:
        return {
            row['code']: Airport(
                code=row['code'], name=row['name'], city=row['city'], country=row['country'],
                lat=float(row['lat']), lon=float(row['lon']), size=row['size'],
            )
            for row in csv.DictReader(f)
        }


def get(code):
    return _airports().get((code or '').strip().upper())


def search(query, limit=10):
    """Exact code first, then code prefixes, then name/city matches; bigger airports win ties."""
    q = (query or '').strip().upper()
    if not q:
        return []
    matches = []
    for airport in _airports().values():
        if airport.code.startswith(q):
            score = 0 if airport.code == q else 1
        elif q in airport.name.upper() or q in airport.city.upper():
            score = 2
        else:
            continue
        matches.append((score, SIZE_RANK.get(airport.size, 9), airport.code, airport))
    matches.sort(key=lambda m: m[:3])
    return [m[3] for m in matches[:limit]]


def distance_nm(a, b):
    """Great-circle distance between two airports, rounded to whole nautical miles."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return round(2 * EARTH_RADIUS_NM * math.asin(math.sqrt(h)))
