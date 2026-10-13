"use client";

import { useState } from 'react';
import Avatar from '@/components/Avatar';
import { Section } from '@/components/PageShell';
import type { CrewInvite, CrewRole, CrewSeat } from '@/types/flight';
import { acceptCrewInvite, addCrew, endCrewSeat, getCrew, getCrewInvites, setMyCrewRole } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const ROLES: Record<CrewRole, string> = { PIC: 'Captain (PIC)', SIC: 'First officer (SIC)' };
const STATUS: Record<CrewSeat['status'], string> = { LOGGER: 'Logged it', PENDING: 'Invited', ACCEPTED: 'In their logbook', DECLINED: 'Declined' };

function useAction() {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const run = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError('');
        try {
            await action();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
        } finally {
            setBusy(false);
        }
    };
    return { busy, error, run };
}

export function CrewSection({ flightId }: { flightId: number }) {
    const { data: crew, setData } = useApi(() => getCrew(flightId), String(flightId));
    const [username, setUsername] = useState('');
    const [role, setRole] = useState<CrewRole>('SIC');
    const { busy, error, run } = useAction();

    if (!crew) return null;
    const me = crew.find((seat) => seat.is_me);
    const isLogger = !me || me.status === 'LOGGER';

    const invite = (e: React.FormEvent) => {
        e.preventDefault();
        run(() => addCrew(flightId, username.trim(), role).then((seats) => {
            setData(() => seats);
            setUsername('');
        }));
    };

    return (
        <Section title="Crew">
            {crew.length > 0 && (
                <ul className="space-y-3">
                    {crew.map((seat) => (
                        <li key={seat.id} className="flex items-center gap-3 text-sm">
                            <Avatar username={seat.username} avatar={seat.avatar} />
                            <div className="min-w-0 flex-1">
                                <p className="text-bone">{seat.username}{seat.is_me && <span className="text-ash"> · you</span>}</p>
                                <p className="text-xs text-ash">{ROLES[seat.role]} · {STATUS[seat.status]}</p>
                            </div>
                            {seat.is_me && (
                                <select
                                    aria-label="My role"
                                    value={seat.role}
                                    disabled={busy}
                                    onChange={(e) => run(() => setMyCrewRole(flightId, e.target.value as CrewRole).then((seats) => setData(() => seats)))}
                                    className="field-input w-auto py-1.5 text-sm"
                                >
                                    {Object.entries(ROLES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                                </select>
                            )}
                            {isLogger && seat.status === 'PENDING' && (
                                <button
                                    onClick={() => run(() => endCrewSeat(seat.id).then(() => setData((seats) => seats?.filter((s) => s.id !== seat.id) ?? null)))}
                                    disabled={busy}
                                    className="btn btn-ghost py-1.5 text-sm"
                                >
                                    Cancel
                                </button>
                            )}
                        </li>
                    ))}
                </ul>
            )}
            {error && <p className="alert-error mt-3" role="alert">{error}</p>}
            {isLogger && (
                <form onSubmit={invite} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
                    <div>
                        <label htmlFor="crew-username" className="field-label">Add a pilot who flew with you</label>
                        <input id="crew-username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Their AirFleet username" autoComplete="off" className="field-input" />
                    </div>
                    <div>
                        <label htmlFor="crew-role" className="field-label">As</label>
                        <select id="crew-role" value={role} onChange={(e) => setRole(e.target.value as CrewRole)} className="field-input">
                            {Object.entries(ROLES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={busy || !username.trim()}>{busy ? 'Inviting…' : 'Invite'}</button>
                </form>
            )}
            <p className="mt-3 text-xs text-ash">
                When they accept, AirFleet adds this flight to their logbook and credits the whole block time to their role. Your notes, photo and landings stay with you.
            </p>
        </Section>
    );
}

function InviteRow({ invite, onDone, onAccepted }: { invite: CrewInvite; onDone: () => void; onAccepted: () => void }) {
    const { busy, error, run } = useAction();
    const { flight } = invite;
    return (
        <li className="card flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <p className="text-bone">{invite.invited_by} added you as {ROLES[invite.role]}</p>
                <p className="mt-1 text-xs text-ash">
                    {flight.departure_airport} → {flight.arrival_airport} · {formatDate(flight.departure_time)} · {flight.registration_number}
                </p>
                {error && <p className="alert-error mt-2" role="alert">{error}</p>}
            </div>
            <div className="flex gap-2">
                <button onClick={() => run(() => acceptCrewInvite(invite.id).then(() => { onDone(); onAccepted(); }))} disabled={busy} className="btn btn-primary">Add to my logbook</button>
                <button onClick={() => run(() => endCrewSeat(invite.id).then(onDone))} disabled={busy} className="btn btn-ghost">Decline</button>
            </div>
        </li>
    );
}

export function CrewInvites({ onAccepted }: { onAccepted: () => void }) {
    const { data: invites, reload } = useApi(getCrewInvites, 'crew-invites');
    if (!invites?.length) return null;
    return (
        <section className="mt-8 animate-rise" aria-label="Crew invites">
            <h2 className="eyebrow mb-3 text-clay">Crew invites</h2>
            <ul className="space-y-3">
                {invites.map((invite) => (
                    <InviteRow key={invite.id} invite={invite} onDone={reload} onAccepted={onAccepted} />
                ))}
            </ul>
            <p className="mt-2 text-xs text-ash">Accepting adds a copy to your logbook that you can edit.</p>
        </section>
    );
}
