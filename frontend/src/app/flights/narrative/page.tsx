"use client";

import { useState } from 'react';
import Link from 'next/link';
import { PageShell, PageHeader, EmptyState, ErrorState, Spinner } from '@/components/PageShell';
import { PlaneIcon } from '@/components/Icons';
import type { Flight } from '@/types/flight';
import { generateNarrative, getFlights } from '@/utils/api';
import { formatDate, formatDuration, formatTime } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const PAGE_SIZE = 10;

function Story({ flight, index, onWritten }: { flight: Flight; index: number; onWritten: (narrative: string) => void }) {
    const [writing, setWriting] = useState(false);
    const [error, setError] = useState('');

    const write = async () => {
        setWriting(true);
        setError('');
        try {
            onWritten((await generateNarrative(flight.id)).narrative);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to generate narrative. Please try again later.');
        } finally {
            setWriting(false);
        }
    };

    return (
        <article
            className="card grid overflow-hidden md:grid-cols-[13rem_1fr] animate-rise"
            style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
        >
            <aside className="flex flex-col gap-4 border-b border-line bg-graphite/40 p-5 md:border-b-0 md:border-r">
                <p className="eyebrow">{formatDate(flight.departure_time, 'long')}</p>
                <Link href={`/flights/${flight.id}`} className="flex items-center gap-2 font-mono text-2xl font-medium tracking-wider text-paper hover:text-fern">
                    {flight.departure_airport}
                    <PlaneIcon className="h-4 w-4 rotate-90 text-moss" />
                    {flight.arrival_airport}
                </Link>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm md:grid-cols-1">
                    <div>
                        <dt className="eyebrow">Off / On</dt>
                        <dd className="mt-0.5 font-mono text-bone">{formatTime(flight.departure_time)} – {formatTime(flight.arrival_time)}</dd>
                    </div>
                    <div>
                        <dt className="eyebrow">Duration</dt>
                        <dd className="mt-0.5 text-bone">{formatDuration(flight.total_time)}</dd>
                    </div>
                    <div>
                        <dt className="eyebrow">Distance</dt>
                        <dd className="mt-0.5 text-bone">{flight.distance.toLocaleString()} nm</dd>
                    </div>
                </dl>
            </aside>

            <div className="p-6 sm:p-8">
                <div className="mb-4 flex items-center justify-between gap-3">
                    <h2 className="eyebrow text-clay">Debrief</h2>
                    <button onClick={write} disabled={writing} className="btn btn-ghost px-3 py-1 text-xs">
                        {writing ? 'Writing…' : flight.narrative ? 'Rewrite' : 'Write the story'}
                    </button>
                </div>
                {error && <p className="alert-error mb-4" role="alert">{error}</p>}
                {writing ? (
                    <div className="space-y-3" role="status" aria-label="Generating narrative">
                        <div className="h-3 w-11/12 animate-pulse rounded bg-graphite" />
                        <div className="h-3 w-full animate-pulse rounded bg-graphite [animation-delay:150ms]" />
                        <div className="h-3 w-4/5 animate-pulse rounded bg-graphite [animation-delay:300ms]" />
                        <p className="pt-2 font-display text-sm italic text-ash">Writing it down…</p>
                    </div>
                ) : flight.narrative ? (
                    <p className="font-display text-lg font-light leading-relaxed text-bone first-letter:float-left first-letter:mr-2 first-letter:font-display first-letter:text-5xl first-letter:font-medium first-letter:leading-[0.9] first-letter:text-fern">
                        {flight.narrative}
                    </p>
                ) : (
                    <p className="font-display text-sm italic text-ash">This leg hasn&apos;t been written up yet.</p>
                )}
            </div>
        </article>
    );
}

export default function FlightNarrativePage() {
    const [page, setPage] = useState(1);
    const { data, error, reload, setData } = useApi(() => getFlights({ page, page_size: PAGE_SIZE }), String(page));
    const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1;

    const saveNarrative = (id: number, narrative: string) =>
        setData((current) => current && { ...current, results: current.results.map((f) => (f.id === id ? { ...f, narrative } : f)) });

    return (
        <PageShell>
            <PageHeader
                eyebrow="Stories"
                title="Flight narratives"
                description="Each entry in your logbook, retold as a short story. Stories are saved once written."
            />

            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !data ? (
                <Spinner label="Gathering your flights" />
            ) : data.count === 0 ? (
                <EmptyState title="No stories yet">
                    <p>Once you log a flight, its story can be written here.</p>
                </EmptyState>
            ) : (
                <>
                    <div className="space-y-6">
                        {data.results.map((flight, i) => (
                            <Story key={flight.id} flight={flight} index={i} onWritten={(narrative) => saveNarrative(flight.id, narrative)} />
                        ))}
                    </div>
                    {pages > 1 && (
                        <nav className="mt-8 flex items-center justify-between gap-4" aria-label="Story pages">
                            <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className="btn btn-ghost">← Newer</button>
                            <span className="eyebrow">Page {page} of {pages}</span>
                            <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages} className="btn btn-ghost">Older →</button>
                        </nav>
                    )}
                </>
            )}
        </PageShell>
    );
}
