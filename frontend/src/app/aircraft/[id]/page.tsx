"use client";

import { use, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AircraftForm, { InspectionBar, maintenanceStatus } from '@/components/AircraftForm';
import { EditIcon, PlaneIcon, TrashIcon, WrenchIcon } from '@/components/Icons';
import { ErrorState, PageHeader, PageShell, Section, Spinner, StatGrid } from '@/components/PageShell';
import type { Aircraft } from '@/types/flight';
import { deleteAircraft, getAircraft, getFlights, logMaintenance, updateAircraft } from '@/utils/api';
import { AIRCRAFT_CLASSES, formatDate, formatDuration, fromLocalInput, toLocalInput } from '@/utils/format';
import { useApi } from '@/utils/useApi';

function MaintenanceForm({ aircraft, onLogged }: { aircraft: Aircraft; onLogged: (a: Aircraft) => void }) {
    const [performedAt, setPerformedAt] = useState(() => toLocalInput(new Date().toISOString()));
    const [annualDue, setAnnualDue] = useState(aircraft.annual_due ?? '');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            onLogged(await logMaintenance(aircraft.id, { performed_at: fromLocalInput(performedAt), annual_due: annualDue || undefined }));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not log maintenance');
        } finally {
            setSaving(false);
        }
    };

    return (
        <form onSubmit={submit} className="card grid gap-4 p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            {error && <p className="alert-error sm:col-span-3" role="alert">{error}</p>}
            <div>
                <label htmlFor="performed_at" className="field-label">Completed</label>
                <input id="performed_at" type="datetime-local" value={performedAt} onChange={(e) => setPerformedAt(e.target.value)} required className="field-input" />
            </div>
            <div>
                <label htmlFor="annual_due_next" className="field-label">Next annual due</label>
                <input id="annual_due_next" type="date" value={annualDue} onChange={(e) => setAnnualDue(e.target.value)} className="field-input" />
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>
                <WrenchIcon className="h-4 w-4" />
                {saving ? 'Saving…' : 'Log maintenance'}
            </button>
            <p className="text-xs text-ash sm:col-span-3">
                Resets the hours counter{aircraft.grounded ? ' and returns the aircraft to service' : ''}.
            </p>
        </form>
    );
}

export default function AircraftPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const { data: aircraft, error, reload, setData } = useApi(() => getAircraft(id), id);
    const flights = useApi(
        () => (aircraft ? getFlights({ aircraft: aircraft.registration, page_size: 10 }) : Promise.resolve(null)),
        aircraft?.registration ?? '',
    );
    const [editing, setEditing] = useState(false);

    if (error || !aircraft) {
        return <PageShell>{error ? <ErrorState message={error} onRetry={reload} /> : <Spinner label="Opening the hangar" />}</PageShell>;
    }

    const status = maintenanceStatus(aircraft);

    const remove = async () => {
        if (!window.confirm(`Remove ${aircraft.registration} from your fleet? Its flights stay in your logbook.`)) return;
        await deleteAircraft(aircraft.id);
        router.push('/aircraft');
    };

    return (
        <PageShell>
            <PageHeader
                eyebrow={`Fleet · ${AIRCRAFT_CLASSES[aircraft.aircraft_class] ?? aircraft.aircraft_class}`}
                title={aircraft.registration}
                description={[aircraft.type_code, aircraft.make_model].filter(Boolean).join(' · ') || undefined}
                action={
                    <div className="flex flex-wrap gap-2">
                        <button onClick={() => setEditing((v) => !v)} className="btn btn-ghost">
                            <EditIcon className="h-4 w-4" />
                            Edit
                        </button>
                        <button onClick={remove} className="btn btn-ghost hover:border-rust/60 hover:text-[#e7b6a1]">
                            <TrashIcon className="h-4 w-4" />
                            Remove
                        </button>
                    </div>
                }
            />

            {editing && (
                <div className="mb-8 animate-rise">
                    <AircraftForm
                        aircraft={aircraft}
                        submitLabel="Save aircraft"
                        onCancel={() => setEditing(false)}
                        onSubmit={async (data) => {
                            const updated = await updateAircraft(aircraft.id, data);
                            setData(() => updated);
                            setEditing(false);
                            flights.reload();
                        }}
                    />
                </div>
            )}

            <StatGrid
                stats={[
                    { label: 'Flights', value: aircraft.total_flights.toLocaleString() },
                    { label: 'Total time', value: formatDuration(aircraft.total_time) },
                    { label: 'Last inspection', value: aircraft.last_maintenance_at ? formatDate(aircraft.last_maintenance_at) : '—' },
                    { label: 'Annual due', value: aircraft.annual_due ? formatDate(aircraft.annual_due) : '—' },
                ]}
            />

            <Section title="Maintenance" action={<span className={`rounded-full border px-2.5 py-0.5 text-xs ${status.tone}`}>{status.label}</span>}>
                {aircraft.grounded && (
                    <p className="alert-error mb-4" role="alert">
                        A flight reported this aircraft as grounded. New flights in it are blocked until you log maintenance.
                    </p>
                )}
                <div className="mb-5">
                    <InspectionBar aircraft={aircraft} />
                </div>
                <MaintenanceForm key={aircraft.last_maintenance_at ?? 'never'} aircraft={aircraft} onLogged={(updated) => setData(() => updated)} />
            </Section>

            {aircraft.notes && (
                <Section title="Notes">
                    <p className="whitespace-pre-line text-bone">{aircraft.notes}</p>
                </Section>
            )}

            <Section
                title="Recent flights"
                action={
                    flights.data && flights.data.count > 10 ? (
                        <Link href="/flights" className="text-xs text-fern hover:underline">All {flights.data.count} in the logbook</Link>
                    ) : undefined
                }
            >
                {!flights.data ? (
                    <p className="text-sm text-ash">Loading…</p>
                ) : flights.data.results.length === 0 ? (
                    <p className="text-sm text-ash">No flights logged in {aircraft.registration} yet.</p>
                ) : (
                    <ul className="divide-y divide-line rounded-xl border border-line">
                        {flights.data.results.map((f) => (
                            <li key={f.id}>
                                <Link href={`/flights/${f.id}`} className="flex items-center justify-between gap-4 px-4 py-3 text-sm transition-colors hover:bg-graphite/50">
                                    <span className="flex items-center gap-2 font-mono text-bone">
                                        {f.departure_airport}
                                        <PlaneIcon className="h-3.5 w-3.5 rotate-90 text-moss" />
                                        {f.arrival_airport}
                                    </span>
                                    <span className="text-ash">{formatDate(f.departure_time)}</span>
                                    <span className="font-mono text-stone">{formatDuration(f.total_time)}</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                )}
            </Section>
        </PageShell>
    );
}
