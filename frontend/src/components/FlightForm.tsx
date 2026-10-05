"use client";

import { useEffect, useState, useSyncExternalStore } from 'react';
import Link from 'next/link';
import AirportInput from '@/components/AirportInput';
import { CameraIcon, CloudIcon, UploadIcon } from '@/components/Icons';
import type { Airport, Flight } from '@/types/flight';
import { getFleet, getMetar, getSimbrief } from '@/utils/api';
import { CONDITIONS, distanceNm, durationInput, formatHours, fromLocalInput, parseDurationInput, toLocalInput } from '@/utils/format';

const TIME_FIELDS = [
    ['pic_time', 'PIC'],
    ['sic_time', 'SIC'],
    ['dual_received_time', 'Dual received'],
    ['night_time', 'Night'],
    ['instrument_time', 'Actual instrument'],
    ['simulated_instrument_time', 'Simulated instrument'],
] as const;
type TimeField = (typeof TIME_FIELDS)[number][0];

const COUNT_FIELDS = [
    ['day_landings', 'Day landings'],
    ['night_landings', 'Night landings'],
    ['approaches', 'Approaches'],
] as const;
type CountField = (typeof COUNT_FIELDS)[number][0];

type FormState = {
    departure_time: string;
    arrival_time: string;
    departure_airport: string;
    arrival_airport: string;
    distance: string;
    departure_gate: string;
    arrival_gate: string;
    flight_plan: string;
    registration_number: string;
    aircraft_condition: string;
    is_simulator: boolean;
    cross_country: boolean;
    weather_conditions: string;
    notes: string;
} & Record<TimeField, string> & Record<CountField, string>;

const SIMBRIEF_KEY = 'airfleet.simbriefUser';

// The last SimBrief username, remembered per browser. Read through useSyncExternalStore so the
// server render (no storage) and hydration agree.
const readSimbriefUser = () => {
    try {
        return window.localStorage.getItem(SIMBRIEF_KEY) ?? '';
    } catch {
        return '';
    }
};
const noSubscription = () => () => {};

function initialState(flight?: Flight): FormState {
    return {
        departure_time: toLocalInput(flight?.departure_time),
        arrival_time: toLocalInput(flight?.arrival_time),
        departure_airport: flight?.departure_airport ?? '',
        arrival_airport: flight?.arrival_airport ?? '',
        distance: flight ? String(flight.distance) : '',
        departure_gate: flight?.departure_gate ?? '',
        arrival_gate: flight?.arrival_gate ?? '',
        flight_plan: flight?.flight_plan ?? '',
        registration_number: flight?.registration_number ?? '',
        aircraft_condition: flight?.aircraft_condition ?? 'AIRWORTHY',
        is_simulator: flight?.is_simulator ?? false,
        cross_country: flight?.cross_country ?? false,
        weather_conditions: flight?.weather_conditions ?? '',
        notes: flight?.notes ?? '',
        pic_time: durationInput(flight?.pic_time),
        sic_time: durationInput(flight?.sic_time),
        dual_received_time: durationInput(flight?.dual_received_time),
        night_time: durationInput(flight?.night_time),
        instrument_time: durationInput(flight?.instrument_time),
        simulated_instrument_time: durationInput(flight?.simulated_instrument_time),
        day_landings: flight ? String(flight.day_landings) : '1',
        night_landings: flight ? String(flight.night_landings) : '0',
        approaches: flight ? String(flight.approaches) : '0',
    };
}

export default function FlightForm({
    flight,
    submitLabel,
    onSubmit,
    cancelHref,
}: {
    flight?: Flight;
    submitLabel: string;
    onSubmit: (data: FormData) => Promise<void>;
    cancelHref: string;
}) {
    const [form, setForm] = useState<FormState>(() => initialState(flight));
    const [photo, setPhoto] = useState<File | null>(null);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);
    const [fleet, setFleet] = useState<string[]>([]);
    const [departure, setDeparture] = useState<Airport | null>(null);
    const [arrival, setArrival] = useState<Airport | null>(null);
    const [metarStatus, setMetarStatus] = useState('');
    const savedSimbriefUser = useSyncExternalStore(noSubscription, readSimbriefUser, () => '');
    const [simbriefInput, setSimbriefUser] = useState<string | null>(null);
    const simbriefUser = simbriefInput ?? savedSimbriefUser;
    const [simbriefStatus, setSimbriefStatus] = useState('');

    useEffect(() => {
        getFleet().then((planes) => setFleet(planes.map((p) => p.registration))).catch(() => {});
    }, []);

    const set = <K extends keyof FormState>(name: K, value: FormState[K]) => setForm((prev) => ({ ...prev, [name]: value }));
    // A changed route makes the saved distance stale; blank it so the server recomputes it.
    const setAirport = (name: 'departure_airport' | 'arrival_airport', code: string) =>
        setForm((prev) => ({
            ...prev,
            [name]: code,
            distance: flight && code !== flight[name] && prev.distance === String(flight.distance) ? '' : prev.distance,
        }));
    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const { name, value, type } = e.target;
        set(name as keyof FormState, (type === 'checkbox' ? (e.target as HTMLInputElement).checked : value) as never);
    };

    const blockSeconds = form.departure_time && form.arrival_time
        ? (new Date(form.arrival_time).getTime() - new Date(form.departure_time).getTime()) / 1000
        : 0;
    const blockTimeValid = blockSeconds > 0;
    const blockLabel = !form.departure_time || !form.arrival_time ? '—' : blockTimeValid ? formatHours(blockSeconds) : 'Check times';
    const blockHM = `${Math.floor(blockSeconds / 3600)}:${String(Math.floor((blockSeconds % 3600) / 60)).padStart(2, '0')}`;
    const estimatedDistance = departure && arrival ? distanceNm(departure, arrival) : null;

    const fetchMetar = async () => {
        if (form.departure_airport.length !== 4) {
            setMetarStatus('Enter the departure airport first.');
            return;
        }
        setMetarStatus('Fetching…');
        try {
            const report = await getMetar(form.departure_airport, form.departure_time ? fromLocalInput(form.departure_time) : undefined);
            set('weather_conditions', report.raw);
            setMetarStatus(report.flight_category ? `${report.flight_category} conditions` : 'Added');
        } catch (e) {
            setMetarStatus(e instanceof Error ? e.message : 'No METAR found');
        }
    };

    const importSimbrief = async () => {
        if (!simbriefUser.trim()) return;
        setSimbriefStatus('Fetching your latest OFP…');
        try {
            const plan = await getSimbrief(simbriefUser.trim());
            try {
                window.localStorage.setItem(SIMBRIEF_KEY, simbriefUser.trim());
            } catch {
                // Only a convenience; fine if storage is blocked.
            }
            setForm((prev) => ({
                ...prev,
                departure_airport: plan.departure_airport ?? prev.departure_airport,
                arrival_airport: plan.arrival_airport ?? prev.arrival_airport,
                departure_time: toLocalInput(plan.departure_time) || prev.departure_time,
                arrival_time: toLocalInput(plan.arrival_time) || prev.arrival_time,
                registration_number: plan.registration_number || prev.registration_number,
                flight_plan: plan.flight_plan || prev.flight_plan,
                distance: plan.distance ? String(plan.distance) : prev.distance,
                weather_conditions: plan.weather_conditions || prev.weather_conditions,
                is_simulator: true,
            }));
            setSimbriefStatus(`Loaded ${plan.departure_airport} → ${plan.arrival_airport}. Check the times before saving.`);
        } catch (e) {
            setSimbriefStatus(e instanceof Error ? e.message : 'Could not reach SimBrief');
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!blockTimeValid) {
            setError('Arrival must be after departure.');
            return;
        }
        const data = new FormData();
        data.append('departure_time', fromLocalInput(form.departure_time));
        data.append('arrival_time', fromLocalInput(form.arrival_time));
        for (const key of ['departure_airport', 'arrival_airport', 'registration_number', 'aircraft_condition', 'departure_gate', 'arrival_gate', 'flight_plan', 'weather_conditions', 'notes'] as const) {
            data.append(key, form[key].trim());
        }
        // Blank distance lets the server work it out from the airports.
        data.append('distance', form.distance.trim() || '0');
        data.append('is_simulator', String(form.is_simulator));
        data.append('cross_country', String(form.cross_country));
        for (const [key, label] of TIME_FIELDS) {
            const parsed = parseDurationInput(form[key]);
            if (parsed === null) {
                setError(`${label} time should look like 1:30 or 1.5.`);
                return;
            }
            data.append(key, parsed);
        }
        for (const [key] of COUNT_FIELDS) data.append(key, form[key] || '0');
        if (photo) data.append('photo', photo);

        setSaving(true);
        try {
            await onSubmit(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save the flight. Please try again.');
            setSaving(false);
        }
    };

    const text = (name: keyof FormState, label: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
        <div>
            <label htmlFor={name} className="field-label">{label}</label>
            <input type="text" id={name} name={name} value={form[name] as string} onChange={handleChange} className="field-input" {...extra} />
        </div>
    );

    const toggle = (name: 'is_simulator' | 'cross_country', label: string, hint: string) => (
        <label htmlFor={name} className="flex cursor-pointer items-start gap-3 rounded-lg border border-line px-4 py-3 transition-colors hover:border-ash/60">
            <input type="checkbox" id={name} name={name} checked={form[name]} onChange={handleChange} className="mt-1 h-4 w-4 accent-[var(--color-moss)]" />
            <span>
                <span className="block text-sm text-bone">{label}</span>
                <span className="block text-xs text-ash">{hint}</span>
            </span>
        </label>
    );

    return (
        <form onSubmit={handleSubmit} className="space-y-6 animate-rise">
            {error && <div className="alert-error" role="alert">{error}</div>}

            {!flight && (
                <div className="card flex flex-col gap-3 p-5 sm:flex-row sm:items-end sm:p-6">
                    <div className="flex-1">
                        <label htmlFor="simbrief" className="field-label">Fill from SimBrief</label>
                        <input
                            id="simbrief"
                            value={simbriefUser}
                            onChange={(e) => setSimbriefUser(e.target.value)}
                            placeholder="Your SimBrief username"
                            className="field-input"
                        />
                        {simbriefStatus && <p className="mt-1.5 text-xs text-ash" aria-live="polite">{simbriefStatus}</p>}
                    </div>
                    <button type="button" onClick={importSimbrief} className="btn btn-ghost" disabled={!simbriefUser.trim()}>
                        <UploadIcon className="h-4 w-4" />
                        Load latest flight plan
                    </button>
                </div>
            )}

            <fieldset className="card p-5 sm:p-6">
                <legend className="sr-only">Times</legend>
                <p className="eyebrow mb-5 text-clay">01 · Times</p>
                <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_1fr_auto] md:items-end">
                    <div>
                        <label htmlFor="departure_time" className="field-label">Departure (your local time)</label>
                        <input type="datetime-local" id="departure_time" name="departure_time" value={form.departure_time} onChange={handleChange} required className="field-input" />
                    </div>
                    <div>
                        <label htmlFor="arrival_time" className="field-label">Arrival (your local time)</label>
                        <input type="datetime-local" id="arrival_time" name="arrival_time" value={form.arrival_time} onChange={handleChange} required className="field-input" />
                    </div>
                    <div className="rounded-lg border border-dashed border-line px-4 py-2.5 md:min-w-36">
                        <p className="eyebrow">Block time</p>
                        <p className={`font-mono text-lg ${blockTimeValid ? 'text-fern' : 'text-ash'}`} aria-live="polite">{blockLabel}</p>
                    </div>
                </div>
            </fieldset>

            <fieldset className="card p-5 sm:p-6">
                <legend className="sr-only">Route</legend>
                <p className="eyebrow mb-5 text-clay">02 · Route</p>
                <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                    <AirportInput id="departure_airport" label="From" value={form.departure_airport} onChange={(v) => setAirport('departure_airport', v)} onResolve={setDeparture} placeholder="e.g. KSFO" />
                    <AirportInput id="arrival_airport" label="To" value={form.arrival_airport} onChange={(v) => setAirport('arrival_airport', v)} onResolve={setArrival} placeholder="e.g. KLAX" />
                    <div>
                        <label htmlFor="distance" className="field-label">Distance (nm)</label>
                        <input
                            type="number"
                            id="distance"
                            name="distance"
                            value={form.distance}
                            onChange={handleChange}
                            min="0"
                            placeholder={estimatedDistance !== null ? String(estimatedDistance) : 'Worked out for you'}
                            className="field-input font-mono"
                        />
                        <p className="mt-1.5 text-xs text-ash">
                            {estimatedDistance !== null ? `Great circle: ${estimatedDistance.toLocaleString()} nm. Leave blank to use it.` : 'Leave blank to use the great-circle distance.'}
                        </p>
                    </div>
                </div>
                <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-[1fr_1fr_2fr]">
                    {text('departure_gate', 'Departure gate', { maxLength: 10 })}
                    {text('arrival_gate', 'Arrival gate', { maxLength: 10 })}
                    {text('flight_plan', 'Route / flight plan', { placeholder: 'e.g. DCT SFO V25 LAX' })}
                </div>
            </fieldset>

            <fieldset className="card p-5 sm:p-6">
                <legend className="sr-only">Aircraft</legend>
                <p className="eyebrow mb-5 text-clay">03 · Aircraft</p>
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    <div>
                        <label htmlFor="registration_number" className="field-label">Registration</label>
                        <input
                            type="text"
                            id="registration_number"
                            name="registration_number"
                            list="fleet"
                            value={form.registration_number}
                            onChange={(e) => set('registration_number', e.target.value.toUpperCase())}
                            required
                            maxLength={10}
                            placeholder="e.g. N172SP"
                            className="field-input font-mono uppercase tracking-wider placeholder:normal-case placeholder:tracking-normal"
                        />
                        <datalist id="fleet">
                            {fleet.map((reg) => <option key={reg} value={reg} />)}
                        </datalist>
                    </div>
                    <div>
                        <label htmlFor="aircraft_condition" className="field-label">Condition after the flight</label>
                        <select id="aircraft_condition" name="aircraft_condition" value={form.aircraft_condition} onChange={handleChange} className="field-input">
                            {Object.entries(CONDITIONS).map(([value, { label }]) => (
                                <option key={value} value={value}>{label}</option>
                            ))}
                        </select>
                        {form.aircraft_condition === 'GROUNDED' && (
                            <p className="mt-1.5 text-xs text-clay">The aircraft will be grounded until you log its maintenance.</p>
                        )}
                    </div>
                </div>
                <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
                    {toggle('is_simulator', 'Simulator session', 'Flown in a sim. Doesn’t count towards passenger currency.')}
                    {toggle('cross_country', 'Cross-country', 'Counts towards cross-country time.')}
                </div>

                <label
                    htmlFor="photo"
                    className="mt-5 flex cursor-pointer items-center gap-4 rounded-lg border border-dashed border-line px-4 py-4 transition-colors hover:border-moss/60 hover:bg-graphite/50 focus-within:border-moss"
                >
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-graphite text-moss">
                        <CameraIcon className="h-5 w-5" />
                    </span>
                    <span className="min-w-0">
                        <span className="block text-sm text-bone">
                            {photo ? photo.name : flight?.photo ? 'Replace the photo from this flight' : 'Add a photo from this flight'}
                        </span>
                        <span className="block text-xs text-ash">
                            {photo ? 'Click to choose a different image' : 'Optional · JPEG, PNG, WebP or HEIC up to 10 MB'}
                        </span>
                    </span>
                    <input
                        type="file"
                        id="photo"
                        name="photo"
                        onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
                        accept="image/jpeg,image/png,image/webp,image/gif,image/heic,image/heif"
                        className="sr-only"
                    />
                </label>
            </fieldset>

            <fieldset className="card p-5 sm:p-6">
                <legend className="sr-only">Logbook columns</legend>
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                    <p className="eyebrow text-clay">04 · Logbook columns</p>
                    <button
                        type="button"
                        onClick={() => set('pic_time', blockHM)}
                        disabled={!blockTimeValid}
                        className="btn btn-ghost px-3 py-1 text-xs"
                    >
                        All PIC
                    </button>
                </div>
                <div className="grid grid-cols-2 gap-5 md:grid-cols-3">
                    {TIME_FIELDS.map(([name, label]) => (
                        <div key={name}>
                            <label htmlFor={name} className="field-label">{label}</label>
                            <input
                                type="text"
                                inputMode="decimal"
                                id={name}
                                name={name}
                                value={form[name]}
                                onChange={handleChange}
                                placeholder="0:00"
                                className="field-input font-mono"
                            />
                        </div>
                    ))}
                    {COUNT_FIELDS.map(([name, label]) => (
                        <div key={name}>
                            <label htmlFor={name} className="field-label">{label}</label>
                            <input type="number" id={name} name={name} value={form[name]} onChange={handleChange} min="0" max="999" className="field-input font-mono" />
                        </div>
                    ))}
                </div>
                <p className="mt-4 text-xs text-ash">Times as hours:minutes (1:30) or decimal hours (1.5). None can be longer than the block time.</p>
            </fieldset>

            <fieldset className="card p-5 sm:p-6">
                <legend className="sr-only">Weather and notes</legend>
                <p className="eyebrow mb-5 text-clay">05 · Weather &amp; notes</p>
                <div>
                    <div className="mb-1.5 flex items-end justify-between gap-3">
                        <label htmlFor="weather_conditions" className="field-label mb-0">Weather</label>
                        <button type="button" onClick={fetchMetar} className="btn btn-ghost px-3 py-1 text-xs">
                            <CloudIcon className="h-4 w-4" />
                            Fetch METAR
                        </button>
                    </div>
                    <textarea
                        id="weather_conditions"
                        name="weather_conditions"
                        value={form.weather_conditions}
                        onChange={handleChange}
                        rows={2}
                        placeholder="Paste a METAR or describe the conditions"
                        className="field-input font-mono text-sm"
                    />
                    <p className="mt-1.5 text-xs text-ash" aria-live="polite">
                        {metarStatus || 'Fetches the departure METAR closest to your departure time (last ~2 weeks only).'}
                    </p>
                </div>
                <div className="mt-5">
                    <label htmlFor="notes" className="field-label">Notes</label>
                    <textarea id="notes" name="notes" value={form.notes} onChange={handleChange} rows={4} className="field-input" placeholder="Anything worth remembering" />
                </div>
            </fieldset>

            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <Link href={cancelHref} className="btn btn-ghost">Cancel</Link>
                <button type="submit" className="btn btn-primary px-6" disabled={saving}>
                    {saving ? 'Saving…' : submitLabel}
                </button>
            </div>
        </form>
    );
}
