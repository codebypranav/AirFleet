"use client";

import { use, useState } from 'react';
import Link from 'next/link';
import { EmptyState, ErrorState, PageHeader, PageShell, Spinner } from '@/components/PageShell';
import { DISCLAIMER, SignatureDetails } from '@/components/Signature';
import type { Signature, StudentFlight } from '@/types/flight';
import { getInstructorLinks, getStudentFlights, signFlight } from '@/utils/api';
import { durationToSeconds, formatDate, formatDuration, formatTime } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const PAGE_SIZE = 20;
const COLUMNS: [keyof StudentFlight, string][] = [
    ['dual_received_time', 'Dual received'],
    ['pic_time', 'PIC'],
    ['sic_time', 'SIC'],
    ['night_time', 'Night'],
    ['instrument_time', 'Actual instrument'],
    ['simulated_instrument_time', 'Simulated instrument'],
];

function SignForm({ flight, onSigned }: { flight: StudentFlight; onSigned: (signature: Signature) => void }) {
    const [remarks, setRemarks] = useState('');
    const [agree, setAgree] = useState(false);
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [signing, setSigning] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSigning(true);
        setError('');
        try {
            onSigned(await signFlight(flight.id, { remarks, agree, password }));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not sign this flight');
            setSigning(false);
        }
    };

    const field = (id: string) => `${id}-${flight.id}`;
    return (
        <form onSubmit={submit} className="space-y-4 border-t border-dashed border-line pt-4">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div>
                <label htmlFor={field('remarks')} className="field-label">Remarks (optional)</label>
                <textarea id={field('remarks')} value={remarks} onChange={(e) => setRemarks(e.target.value)} rows={2} maxLength={1000} className="field-input" placeholder="What was covered, what to work on next" />
            </div>
            <label htmlFor={field('agree')} className="flex cursor-pointer items-start gap-3 rounded-lg border border-line px-4 py-3 transition-colors hover:border-ash/60">
                <input type="checkbox" id={field('agree')} checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-4 w-4 accent-[var(--color-moss)]" />
                <span className="text-sm text-bone">{flight.statement}</span>
            </label>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                <div className="sm:w-72">
                    <label htmlFor={field('password')} className="field-label">Your password</label>
                    <input id={field('password')} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="field-input" />
                    <p className="mt-1.5 text-xs text-ash">Leave blank if you only sign in with Google.</p>
                </div>
                <button type="submit" className="btn btn-primary" disabled={signing || !agree}>
                    {signing ? 'Signing…' : 'Sign lesson'}
                </button>
            </div>
        </form>
    );
}

function LessonCard({ flight, onSigned }: { flight: StudentFlight; onSigned: (signature: Signature) => void }) {
    const columns = COLUMNS.filter(([key]) => durationToSeconds(flight[key] as string) > 0);
    const counts = ([
        ['Day landings', flight.day_landings],
        ['Night landings', flight.night_landings],
        ['Approaches', flight.approaches],
    ] as [string, number][]).filter(([, n]) => n > 0);
    const needsSignature = !flight.signature || flight.signature.status !== 'valid';

    return (
        <li className="card space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
                <p className="font-mono text-2xl font-medium tracking-wider text-paper">
                    {flight.departure_airport} → {flight.arrival_airport}
                </p>
                <p className="eyebrow">
                    {formatDate(flight.departure_time, 'long')} · {formatTime(flight.departure_time)}–{formatTime(flight.arrival_time)}
                    {flight.is_simulator && ' · Sim'}
                    {flight.cross_country && ' · XC'}
                </p>
            </div>
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                <div>
                    <dt className="eyebrow">Aircraft</dt>
                    <dd className="mt-1 font-mono text-bone">{flight.registration_number}{flight.aircraft_type && ` · ${flight.aircraft_type}`}</dd>
                </div>
                <div>
                    <dt className="eyebrow">Block time</dt>
                    <dd className="mt-1 text-bone">{formatDuration(flight.total_time)}</dd>
                </div>
                {columns.map(([key, label]) => (
                    <div key={key}>
                        <dt className="eyebrow">{label}</dt>
                        <dd className="mt-1 text-bone">{formatDuration(flight[key] as string)}</dd>
                    </div>
                ))}
                {counts.map(([label, n]) => (
                    <div key={label}>
                        <dt className="eyebrow">{label}</dt>
                        <dd className="mt-1 text-bone">{n}</dd>
                    </div>
                ))}
            </dl>
            {flight.signature && <SignatureDetails signature={flight.signature} viewer="instructor" />}
            {needsSignature && <SignForm flight={flight} onSigned={onSigned} />}
        </li>
    );
}

export default function StudentLessonsPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const [unsignedOnly, setUnsignedOnly] = useState(true);
    const [page, setPage] = useState(1);
    const { data: links } = useApi(getInstructorLinks);
    const flights = useApi(
        () => getStudentFlights(id, { unsigned: unsignedOnly ? 'true' : undefined, page, page_size: PAGE_SIZE }),
        `${id}:${unsignedOnly}:${page}`,
    );
    const student = links?.find((l) => String(l.id) === id && l.role === 'instructor')?.other;
    const pages = flights.data ? Math.max(1, Math.ceil(flights.data.count / PAGE_SIZE)) : 1;

    const markSigned = (flightId: number, signature: Signature) =>
        flights.setData((current) => current && {
            ...current,
            results: current.results.map((f) => (f.id === flightId ? { ...f, signature } : f)),
        });

    return (
        <PageShell>
            <PageHeader
                eyebrow="Instruction · Student"
                title={student ? student.name : 'Lessons'}
                description="Flights where your student logged dual instruction received. Check each entry, then sign it."
                action={<Link href="/instruction" className="btn btn-ghost">All students</Link>}
            />
            <label htmlFor="unsigned_only" className="mb-6 flex cursor-pointer items-center gap-3 text-sm text-stone">
                <input
                    type="checkbox"
                    id="unsigned_only"
                    checked={unsignedOnly}
                    onChange={(e) => {
                        setUnsignedOnly(e.target.checked);
                        setPage(1);
                    }}
                    className="h-4 w-4 accent-[var(--color-moss)]"
                />
                Only lessons waiting for a signature
            </label>

            {flights.error ? (
                <ErrorState message={flights.error} onRetry={flights.reload} />
            ) : !flights.data ? (
                <Spinner label="Opening the lessons" />
            ) : flights.data.results.length === 0 ? (
                <EmptyState title={unsignedOnly ? 'All signed' : 'No lessons yet'}>
                    <p>
                        {unsignedOnly
                            ? 'Nothing is waiting for your signature.'
                            : 'Flights your student logs with dual received time will show up here.'}
                    </p>
                </EmptyState>
            ) : (
                <ol className={`space-y-4 transition-opacity ${flights.loading ? 'opacity-60' : ''}`}>
                    {flights.data.results.map((flight) => (
                        <LessonCard key={flight.id} flight={flight} onSigned={(signature) => markSigned(flight.id, signature)} />
                    ))}
                </ol>
            )}

            {pages > 1 && (
                <nav className="mt-8 flex items-center justify-between gap-4" aria-label="Lesson pages">
                    <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className="btn btn-ghost">← Newer</button>
                    <span className="eyebrow">Page {page} of {pages}</span>
                    <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages} className="btn btn-ghost">Older →</button>
                </nav>
            )}

            <p className="mt-12 text-xs text-ash">{DISCLAIMER}</p>
        </PageShell>
    );
}
