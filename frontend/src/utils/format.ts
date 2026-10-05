import { API_ORIGIN } from '@/utils/api';
import type { Airport } from '@/types/flight';

// The API returns a full signed URL when photos live in object storage,
// and a /media/... path when they're on the backend's local disk.
export const photoUrl = (photo: string) =>
    /^https?:\/\//.test(photo) ? photo : `${API_ORIGIN}${photo}`;

// DRF serializes durations as "[D ]HH:MM:SS[.ffffff]"; str(timedelta) on the
// rankings endpoint gives "[D day[s], ]H:MM:SS".
export const durationToSeconds = (value?: string | null) => {
    const match = value?.match(/^(?:(\d+)(?: days?,)? )?(\d+):(\d{2}):(\d{2})/);
    if (!match) return 0;
    const [, days = '0', h, m, s] = match;
    return Number(days) * 86400 + Number(h) * 3600 + Number(m) * 60 + Number(s);
};

export const formatHours = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m.toString().padStart(2, '0')}m`;
};

export const formatDuration = (value?: string | null) => {
    const seconds = durationToSeconds(value);
    return seconds ? formatHours(seconds) : value || '—';
};

/** "1:30" / "1.5" / "90m" style input → "HH:MM:SS" for the API. Empty → "00:00:00". */
export const parseDurationInput = (value: string): string | null => {
    const text = value.trim();
    if (!text) return '00:00:00';
    let minutes: number;
    if (/^\d+:\d{1,2}$/.test(text)) {
        const [h, m] = text.split(':').map(Number);
        if (m >= 60) return null;
        minutes = h * 60 + m;
    } else if (/^\d*\.?\d+$/.test(text)) {
        minutes = Math.round(Number(text) * 60);
    } else {
        return null;
    }
    const h = Math.floor(minutes / 60);
    return `${String(h).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:00`;
};

/** API duration → "H:MM" for editing; zero → "". */
export const durationInput = (value?: string | null) => {
    const seconds = durationToSeconds(value);
    if (!seconds) return '';
    return `${Math.floor(seconds / 3600)}:${String(Math.floor((seconds % 3600) / 60)).padStart(2, '0')}`;
};

/** ISO timestamp → value for <input type="datetime-local"> in the browser's time zone. */
export const toLocalInput = (iso?: string | null) => {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
};

/** <input type="datetime-local"> value (local time) → ISO timestamp in UTC. */
export const fromLocalInput = (value: string) => (value ? new Date(value).toISOString() : '');

export const formatDate = (iso: string, month: 'short' | 'long' = 'short') =>
    new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month, year: 'numeric' });

export const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });

const EARTH_RADIUS_NM = 3440.065;
const rad = (deg: number) => (deg * Math.PI) / 180;

/** Great-circle distance in nautical miles; matches the backend's calculation. */
export const distanceNm = (a: Pick<Airport, 'lat' | 'lon'>, b: Pick<Airport, 'lat' | 'lon'>) => {
    const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lon - a.lon) / 2) ** 2;
    return Math.round(2 * EARTH_RADIUS_NM * Math.asin(Math.sqrt(h)));
};

/** Points along the great circle from a to b, with longitudes unwrapped so the line never jumps across the map. */
export const greatCircle = (a: Pick<Airport, 'lat' | 'lon'>, b: Pick<Airport, 'lat' | 'lon'>, steps = 64): [number, number][] => {
    const [lat1, lon1, lat2, lon2] = [rad(a.lat), rad(a.lon), rad(b.lat), rad(b.lon)];
    const d = 2 * Math.asin(Math.sqrt(Math.sin((lat2 - lat1) / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin((lon2 - lon1) / 2) ** 2));
    if (d === 0) return [[a.lat, a.lon], [b.lat, b.lon]];
    const points: [number, number][] = [];
    let previous = a.lon;
    for (let i = 0; i <= steps; i++) {
        const f = i / steps;
        const A = Math.sin((1 - f) * d) / Math.sin(d);
        const B = Math.sin(f * d) / Math.sin(d);
        const x = A * Math.cos(lat1) * Math.cos(lon1) + B * Math.cos(lat2) * Math.cos(lon2);
        const y = A * Math.cos(lat1) * Math.sin(lon1) + B * Math.cos(lat2) * Math.sin(lon2);
        const z = A * Math.sin(lat1) + B * Math.sin(lat2);
        let lon = (Math.atan2(y, x) * 180) / Math.PI;
        while (lon - previous > 180) lon -= 360;
        while (lon - previous < -180) lon += 360;
        previous = lon;
        points.push([(Math.atan2(z, Math.sqrt(x * x + y * y)) * 180) / Math.PI, lon]);
    }
    return points;
};

export const CONDITIONS: Record<string, { label: string; className: string }> = {
    AIRWORTHY: { label: 'Airworthy', className: 'border-moss/50 bg-moss/15 text-fern' },
    GOOD: { label: 'Good condition', className: 'border-fern/40 bg-fern/10 text-fern' },
    MINOR_ISSUES: { label: 'Minor issues', className: 'border-sand/40 bg-sand/10 text-sand' },
    MAINTENANCE: { label: 'Needs maintenance', className: 'border-clay/50 bg-clay/15 text-clay' },
    GROUNDED: { label: 'Grounded', className: 'border-rust/50 bg-rust/15 text-[#e7b6a1]' },
};

export const conditionFor = (value: string) =>
    CONDITIONS[value] ?? { label: value, className: 'border-line bg-graphite text-stone' };

export const AIRCRAFT_CLASSES: Record<string, string> = {
    SEL: 'Single-engine land',
    MEL: 'Multi-engine land',
    SES: 'Single-engine sea',
    MES: 'Multi-engine sea',
    HELICOPTER: 'Helicopter',
    GLIDER: 'Glider',
    OTHER: 'Other',
};
