"use client";

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { PageShell, PageHeader, EmptyState, ErrorState, Spinner, StatGrid } from '@/components/PageShell';
import { CameraIcon, DownloadIcon, PlaneIcon, PlusIcon, UploadIcon } from '@/components/Icons';
import { SignatureBadge } from '@/components/Signature';
import { downloadExport, getFlights, getStats, type FlightFilters } from '@/utils/api';
import { conditionFor, formatDate, formatDuration, formatTime, photoUrl } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const EMPTY_FILTERS: FlightFilters = { from: '', to: '', airport: '', aircraft: '', q: '', simulator: '' };
const PAGE_SIZE = 20;

export default function FlightsPage() {
    const [draft, setDraft] = useState<FlightFilters>(EMPTY_FILTERS);
    const [filters, setFilters] = useState<FlightFilters>(EMPTY_FILTERS);
    const [page, setPage] = useState(1);
    const [exporting, setExporting] = useState(false);
    const filterKey = JSON.stringify(filters);

    const flights = useApi(() => getFlights({ ...filters, page, page_size: PAGE_SIZE }), `${filterKey}:${page}`);
    const stats = useApi(() => getStats(filters), filterKey);

    const filtered = Object.values(filters).some(Boolean);
    const totals = stats.data?.totals;
    const pages = flights.data ? Math.max(1, Math.ceil(flights.data.count / PAGE_SIZE)) : 1;

    const applyFilters = (e: React.FormEvent) => {
        e.preventDefault();
        setFilters(draft);
        setPage(1);
    };
    const clearFilters = () => {
        setDraft(EMPTY_FILTERS);
        setFilters(EMPTY_FILTERS);
        setPage(1);
    };
    const exportCsv = async () => {
        setExporting(true);
        try {
            await downloadExport(filters);
        } finally {
            setExporting(false);
        }
    };

    const filterField = (name: keyof FlightFilters, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
        <div>
            <label htmlFor={`filter-${name}`} className="field-label">{label}</label>
            <input
                id={`filter-${name}`}
                value={draft[name]}
                onChange={(e) => setDraft((prev) => ({ ...prev, [name]: e.target.value }))}
                className="field-input py-2 text-sm"
                {...props}
            />
        </div>
    );

    const nothingLogged = !filtered && flights.data?.count === 0;

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook"
                title="My flights"
                description="Every leg you've flown, newest entries first."
                action={
                    <div className="flex flex-wrap gap-2">
                        <Link href="/flights/import" className="btn btn-ghost">
                            <UploadIcon className="h-4 w-4" />
                            Import
                        </Link>
                        <button onClick={exportCsv} disabled={exporting || nothingLogged} className="btn btn-ghost">
                            <DownloadIcon className="h-4 w-4" />
                            {exporting ? 'Exporting…' : 'Export CSV'}
                        </button>
                        <Link href="/flights/add" className="btn btn-primary">
                            <PlusIcon className="h-4 w-4" />
                            Add flight
                        </Link>
                    </div>
                }
            />

            {flights.error ? (
                <ErrorState message={flights.error} onRetry={flights.reload} />
            ) : !flights.data ? (
                <Spinner label="Opening the logbook" />
            ) : nothingLogged ? (
                <EmptyState title="A blank first page">
                    <p>Log your first flight and it will show up here, with time, distance and photos.</p>
                    <div className="mt-6 flex flex-wrap justify-center gap-2">
                        <Link href="/flights/add" className="btn btn-primary">
                            <PlusIcon className="h-4 w-4" />
                            Log a flight
                        </Link>
                        <Link href="/flights/import" className="btn btn-ghost">Import a logbook</Link>
                    </div>
                </EmptyState>
            ) : (
                <>
                    {totals && (
                        <StatGrid
                            stats={[
                                { label: 'Legs', value: totals.flights.toLocaleString() },
                                { label: 'Total time', value: `${totals.hours.toLocaleString()} h` },
                                { label: 'Distance', value: `${totals.distance.toLocaleString()} nm` },
                                { label: 'Airframes', value: totals.airframes.toLocaleString() },
                            ]}
                        />
                    )}

                    <details className="card mt-8 p-5 animate-rise" open={filtered}>
                        <summary className="eyebrow cursor-pointer select-none text-clay">
                            Filter flights{filtered ? ` · ${flights.data.count} match${flights.data.count === 1 ? '' : 'es'}` : ''}
                        </summary>
                        <form onSubmit={applyFilters} className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-3">
                            {filterField('from', 'From date', { type: 'date' })}
                            {filterField('to', 'To date', { type: 'date' })}
                            {filterField('airport', 'Airport', { placeholder: 'e.g. KSFO', maxLength: 4 })}
                            {filterField('aircraft', 'Registration', { placeholder: 'e.g. N172SP' })}
                            {filterField('q', 'Search notes & stories', { placeholder: 'e.g. crosswind' })}
                            <div>
                                <label htmlFor="filter-simulator" className="field-label">Flights</label>
                                <select
                                    id="filter-simulator"
                                    value={draft.simulator}
                                    onChange={(e) => setDraft((prev) => ({ ...prev, simulator: e.target.value }))}
                                    className="field-input py-2 text-sm"
                                >
                                    <option value="">All</option>
                                    <option value="false">Aircraft only</option>
                                    <option value="true">Simulator only</option>
                                </select>
                            </div>
                            <div className="col-span-2 flex justify-end gap-2 md:col-span-3">
                                {filtered && <button type="button" onClick={clearFilters} className="btn btn-ghost">Clear</button>}
                                <button type="submit" className="btn btn-primary">Apply filters</button>
                            </div>
                        </form>
                    </details>

                    {flights.data.results.length === 0 ? (
                        <p className="mt-8 text-center text-sm text-ash">No flights match these filters.</p>
                    ) : (
                        <ol className={`mt-8 space-y-4 transition-opacity ${flights.loading ? 'opacity-60' : ''}`}>
                            {flights.data.results.map((flight, i) => {
                                const condition = conditionFor(flight.aircraft_condition);
                                return (
                                    <li key={flight.id} className="animate-rise" style={{ animationDelay: `${Math.min(i, 8) * 50}ms` }}>
                                        <Link
                                            href={`/flights/${flight.id}`}
                                            className="card group flex flex-col overflow-hidden transition-colors hover:border-ash/50 sm:flex-row"
                                        >
                                            <div className="flex flex-1 flex-col gap-5 p-5 sm:p-6">
                                                <div className="flex flex-wrap items-start justify-between gap-3">
                                                    <p className="eyebrow">
                                                        {formatDate(flight.departure_time)} · {formatTime(flight.departure_time)}
                                                        {flight.is_simulator && ' · Sim'}
                                                        {flight.is_draft && ' · Draft'}
                                                    </p>
                                                    <span className="flex flex-wrap gap-2">
                                                        <SignatureBadge signature={flight.signature} />
                                                        <span className={`rounded-full border px-2.5 py-0.5 text-xs ${condition.className}`}>
                                                            {condition.label}
                                                        </span>
                                                    </span>
                                                </div>

                                                <div className="flex items-center gap-4">
                                                    <span className="font-mono text-3xl font-medium tracking-wider text-paper sm:text-4xl">
                                                        {flight.departure_airport}
                                                    </span>
                                                    <span className="relative flex flex-1 items-center">
                                                        <span className="w-full border-t border-dashed border-ash/50" />
                                                        <PlaneIcon className="absolute left-1/2 h-5 w-5 -translate-x-1/2 rotate-90 bg-char px-0.5 text-moss transition-transform duration-500 group-hover:translate-x-4" />
                                                    </span>
                                                    <span className="font-mono text-3xl font-medium tracking-wider text-paper sm:text-4xl">
                                                        {flight.arrival_airport}
                                                    </span>
                                                </div>

                                                <dl className="grid grid-cols-3 gap-4 border-t border-dashed border-line pt-4 text-sm">
                                                    <div>
                                                        <dt className="eyebrow">Block time</dt>
                                                        <dd className="mt-1 text-bone">{formatDuration(flight.total_time)}</dd>
                                                    </div>
                                                    <div>
                                                        <dt className="eyebrow">Distance</dt>
                                                        <dd className="mt-1 text-bone">{flight.distance.toLocaleString()} nm</dd>
                                                    </div>
                                                    <div>
                                                        <dt className="eyebrow">Aircraft</dt>
                                                        <dd className="mt-1 font-mono text-bone">{flight.registration_number}</dd>
                                                    </div>
                                                </dl>
                                            </div>

                                            {flight.photo ? (
                                                <div className="relative h-48 border-t border-line sm:h-auto sm:w-56 sm:border-l sm:border-t-0">
                                                    <Image
                                                        src={photoUrl(flight.photo)}
                                                        alt={`Photo from ${flight.departure_airport} to ${flight.arrival_airport}`}
                                                        fill
                                                        sizes="(min-width: 640px) 224px, 100vw"
                                                        // Photos are short-lived signed links from Neon Object Storage,
                                                        // so the browser loads them directly instead of via the optimizer.
                                                        unoptimized
                                                        className="object-cover grayscale-[35%] sepia-[15%] transition duration-500 group-hover:grayscale-0 group-hover:sepia-0"
                                                    />
                                                </div>
                                            ) : (
                                                <div className="hidden items-center justify-center border-l border-line bg-graphite/40 text-line sm:flex sm:w-56">
                                                    <CameraIcon className="h-8 w-8" />
                                                </div>
                                            )}
                                        </Link>
                                    </li>
                                );
                            })}
                        </ol>
                    )}

                    {pages > 1 && (
                        <nav className="mt-8 flex items-center justify-between gap-4" aria-label="Logbook pages">
                            <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className="btn btn-ghost">
                                ← Newer
                            </button>
                            <span className="eyebrow">Page {page} of {pages}</span>
                            <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages} className="btn btn-ghost">
                                Older →
                            </button>
                        </nav>
                    )}
                </>
            )}
        </PageShell>
    );
}
