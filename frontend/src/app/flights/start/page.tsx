"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import AirportInput from '@/components/AirportInput';
import { ROLES, useAction } from '@/components/Crew';
import { PageShell, PageHeader } from '@/components/PageShell';
import type { CrewRole } from '@/types/flight';
import { startFlight } from '@/utils/api';
import { durationToSeconds, parseDurationInput } from '@/utils/format';

type Crewmate = { username: string; role: CrewRole };

export default function StartFlightPage() {
    const router = useRouter();
    const { busy, error, run } = useAction();
    const [departure, setDeparture] = useState('');
    const [arrival, setArrival] = useState('');
    const [registration, setRegistration] = useState('');
    const [ete, setEte] = useState('');
    const [role, setRole] = useState<CrewRole>('PIC');
    const [crew, setCrew] = useState<Crewmate[]>([]);

    const setCrewmate = (index: number, change: Partial<Crewmate>) =>
        setCrew((rows) => rows.map((row, i) => (i === index ? { ...row, ...change } : row)));

    const submit = (e: React.FormEvent) => {
        e.preventDefault();
        const minutes = durationToSeconds(parseDurationInput(ete)) / 60;
        run(async () => {
            if (!minutes) throw new Error('Enter the estimated time en route as hh:mm, e.g. 1:30.');
            await startFlight({
                role,
                departure_airport: departure,
                arrival_airport: arrival,
                registration_number: registration,
                ete_minutes: minutes,
                crew: crew.filter((row) => row.username.trim()).map((row) => ({ ...row, username: row.username.trim() })),
            });
            router.push('/flights');
        });
    };

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook · Live"
                title="Start a flight"
                description="The timer starts now. Your crew see the flight while it's in the air, and you finish the details after you land."
            />
            <form onSubmit={submit} className="card grid max-w-2xl grid-cols-1 gap-4 p-6 sm:grid-cols-2">
                <AirportInput id="live-departure" label="From" value={departure} onChange={setDeparture} />
                <AirportInput id="live-arrival" label="To" value={arrival} onChange={setArrival} />
                <div>
                    <label htmlFor="live-registration" className="field-label">Aircraft registration</label>
                    <input id="live-registration" required value={registration} onChange={(e) => setRegistration(e.target.value)} className="field-input" />
                </div>
                <div>
                    <label htmlFor="live-ete" className="field-label">Estimated time en route</label>
                    <input id="live-ete" required value={ete} onChange={(e) => setEte(e.target.value)} placeholder="1:30" className="field-input" />
                </div>
                <div>
                    <label htmlFor="live-role" className="field-label">My role</label>
                    <select id="live-role" value={role} onChange={(e) => setRole(e.target.value as CrewRole)} className="field-input">
                        {Object.entries(ROLES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                </div>
                <fieldset className="sm:col-span-2">
                    <legend className="field-label">Crew</legend>
                    {crew.map((row, index) => (
                        <div key={index} className="mb-2 grid grid-cols-[1fr_auto_auto] gap-2">
                            <input aria-label="Crewmate's username" value={row.username} onChange={(e) => setCrewmate(index, { username: e.target.value })} placeholder="Their AirFleet username" autoComplete="off" className="field-input" />
                            <select aria-label="Their role" value={row.role} onChange={(e) => setCrewmate(index, { role: e.target.value as CrewRole })} className="field-input w-auto">
                                {Object.entries(ROLES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                            </select>
                            <button type="button" onClick={() => setCrew((rows) => rows.filter((_, i) => i !== index))} className="btn btn-ghost">Remove</button>
                        </div>
                    ))}
                    <button type="button" onClick={() => setCrew((rows) => [...rows, { username: '', role: 'SIC' }])} className="btn btn-ghost text-sm">Add crewmate</button>
                </fieldset>
                {error && <p className="alert-error sm:col-span-2" role="alert">{error}</p>}
                <button type="submit" disabled={busy} className="btn btn-primary sm:col-span-2">{busy ? 'Starting…' : 'Start flight'}</button>
            </form>
        </PageShell>
    );
}
