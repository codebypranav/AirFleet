"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAction } from '@/components/Crew';
import type { LiveFlight } from '@/types/flight';
import { deleteFlight, getLiveFlights, landFlight, stillFlying } from '@/utils/api';
import { fromLocalInput, toLocalInput } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const elapsed = (from: string, now: number) => {
    const minutes = Math.max(0, Math.floor((now - Date.parse(from)) / 60000));
    return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
};

function LiveRow({ flight, now, reload }: { flight: LiveFlight; now: number; reload: () => void }) {
    const router = useRouter();
    const { busy, error, run } = useAction();
    const [landedAt, setLandedAt] = useState(toLocalInput(flight.eta));
    const route = `${flight.departure_airport} → ${flight.arrival_airport}`;
    const land = (at?: string) => run(() => landFlight(flight.id, at).then((landed) => router.push(`/flights/${landed.id}/edit`)));
    const discard = () => {
        if (window.confirm('Discard this flight? It won\'t be logged.')) run(() => deleteFlight(flight.id).then(reload));
    };

    return (
        <li className="flex flex-col gap-2 py-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-bone">
                <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-clay" aria-hidden />
                {flight.is_mine ? 'You are flying' : `${flight.pilot} is flying`} {route} · {flight.registration_number} ·{' '}
                <span className="font-mono" aria-label="Time airborne">{elapsed(flight.departure_time, now)}</span>
                {!flight.is_mine && flight.unconfirmed && <span className="text-ash"> · Landing time unconfirmed</span>}
            </p>
            {flight.is_mine && (flight.unconfirmed ? (
                <div className="flex flex-wrap items-end gap-2">
                    <label className="text-xs text-ash">
                        Past your ETA, still flying? Landed at
                        <input type="datetime-local" value={landedAt} onChange={(e) => setLandedAt(e.target.value)} className="field-input ml-2 w-auto py-1 text-sm" />
                    </label>
                    <button onClick={() => land(fromLocalInput(landedAt))} disabled={busy || !landedAt} className="btn btn-primary py-1.5 text-sm">Landed</button>
                    <button onClick={() => run(() => stillFlying(flight.id).then(reload))} disabled={busy} className="btn btn-ghost py-1.5 text-sm">Still flying</button>
                    <button onClick={discard} disabled={busy} className="btn btn-ghost py-1.5 text-sm">Discard</button>
                </div>
            ) : (
                <div className="flex gap-2">
                    <button onClick={() => land()} disabled={busy} className="btn btn-primary py-1.5 text-sm">Land</button>
                    <button onClick={discard} disabled={busy} className="btn btn-ghost py-1.5 text-sm">Discard</button>
                </div>
            ))}
            {error && <p className="alert-error" role="alert">{error}</p>}
        </li>
    );
}

export default function LiveFlights() {
    const { data: flights, reload } = useApi(getLiveFlights, 'live');
    const [now, setNow] = useState(Date.now);
    const live = Boolean(flights?.length);

    useEffect(() => {
        const poll = () => document.visibilityState === 'visible' && reload();
        const timer = setInterval(poll, 30_000);
        document.addEventListener('visibilitychange', poll);
        return () => {
            clearInterval(timer);
            document.removeEventListener('visibilitychange', poll);
        };
    }, [reload]);

    useEffect(() => {
        if (!live) return;
        const timer = setInterval(() => setNow(Date.now()), 1000);
        return () => clearInterval(timer);
    }, [live]);

    if (!flights?.length) return null;
    return (
        <section aria-label="Flights in progress" aria-live="polite" className="relative border-b border-line bg-char/80">
            <ul className="mx-auto w-full max-w-5xl divide-y divide-line px-4 sm:px-6">
                {flights.map((flight) => <LiveRow key={`${flight.id}-${flight.eta}`} flight={flight} now={now} reload={reload} />)}
            </ul>
        </section>
    );
}
