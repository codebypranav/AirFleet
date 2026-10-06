"use client";

import { use, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import RouteMap from '@/components/RouteMap';
import { EditIcon, ShareIcon, TrashIcon } from '@/components/Icons';
import { ErrorState, PageHeader, PageShell, Section, Spinner, StatGrid } from '@/components/PageShell';
import { DISCLAIMER, SignatureBadge, SignatureDetails } from '@/components/Signature';
import type { Flight } from '@/types/flight';
import { deleteFlight, getFlight, getProfile } from '@/utils/api';
import { conditionFor, durationToSeconds, formatDate, formatDuration, formatTime, photoUrl } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const COLUMNS: [keyof Flight, string][] = [
    ['pic_time', 'PIC'],
    ['sic_time', 'SIC'],
    ['dual_received_time', 'Dual received'],
    ['night_time', 'Night'],
    ['instrument_time', 'Actual instrument'],
    ['simulated_instrument_time', 'Simulated instrument'],
];

export default function FlightDetail({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const { data: flight, error, reload } = useApi(() => getFlight(id), id);
    const { data: profile } = useApi(getProfile);
    const [deleting, setDeleting] = useState(false);
    const [copied, setCopied] = useState(false);

    if (error || !flight) {
        return (
            <PageShell>
                {error ? <ErrorState message={error} onRetry={reload} /> : <Spinner label="Opening the entry" />}
            </PageShell>
        );
    }

    const condition = conditionFor(flight.aircraft_condition);
    const columns = COLUMNS.filter(([key]) => durationToSeconds(flight[key] as string) > 0);
    const counts = [
        ['Day landings', flight.day_landings],
        ['Night landings', flight.night_landings],
        ['Approaches', flight.approaches],
    ].filter(([, n]) => Number(n) > 0) as [string, number][];
    const mapData = flight.departure_info && flight.arrival_info
        ? {
            routes: [{ from: flight.departure_airport, to: flight.arrival_airport, flights: 1, hours: 0 }],
            airports: flight.departure_airport === flight.arrival_airport ? [flight.departure_info] : [flight.departure_info, flight.arrival_info],
        }
        : null;

    const handleDelete = async () => {
        if (!window.confirm(`Delete ${flight.departure_airport} → ${flight.arrival_airport} on ${formatDate(flight.departure_time)}? This can't be undone.`)) return;
        setDeleting(true);
        try {
            await deleteFlight(flight.id);
            router.push('/flights');
        } catch {
            setDeleting(false);
        }
    };

    const share = async () => {
        await navigator.clipboard.writeText(`${window.location.origin}/share/flights/${flight.id}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <PageShell>
            <PageHeader
                eyebrow={`${formatDate(flight.departure_time, 'long')}${flight.is_simulator ? ' · Simulator' : ''}${flight.is_draft ? ' · Draft' : ''}`}
                title={`${flight.departure_airport} → ${flight.arrival_airport}`}
                description={[flight.departure_info?.name, flight.arrival_info?.name].filter(Boolean).join(' to ')}
                action={
                    <div className="flex flex-wrap gap-2">
                        {profile?.is_public && (
                            <button onClick={share} className="btn btn-ghost">
                                <ShareIcon className="h-4 w-4" />
                                {copied ? 'Link copied' : 'Share'}
                            </button>
                        )}
                        <Link href={`/flights/${flight.id}/edit`} className="btn btn-ghost">
                            <EditIcon className="h-4 w-4" />
                            Edit
                        </Link>
                        <button onClick={handleDelete} disabled={deleting} className="btn btn-ghost hover:border-rust/60 hover:text-[#e7b6a1]">
                            <TrashIcon className="h-4 w-4" />
                            {deleting ? 'Deleting…' : 'Delete'}
                        </button>
                    </div>
                }
            />

            <StatGrid
                stats={[
                    { label: 'Block time', value: formatDuration(flight.total_time) },
                    { label: 'Distance', value: `${flight.distance.toLocaleString()} nm` },
                    { label: 'Aircraft', value: flight.registration_number + (flight.aircraft_type ? ` · ${flight.aircraft_type}` : '') },
                    { label: 'Off / On', value: `${formatTime(flight.departure_time)}–${formatTime(flight.arrival_time)}` },
                ]}
            />

            <div className="mt-6 flex flex-wrap items-center gap-2 text-xs">
                <span className={`rounded-full border px-2.5 py-0.5 ${condition.className}`}>{condition.label}</span>
                <SignatureBadge signature={flight.signature} />
                {flight.cross_country && <span className="rounded-full border border-line px-2.5 py-0.5 text-stone">Cross-country</span>}
                {flight.is_draft && (
                    <Link href={`/flights/${flight.id}/edit`} className="rounded-full border border-clay/60 px-2.5 py-0.5 text-clay hover:border-clay">
                        Draft · add the actual times to log it
                    </Link>
                )}
                {flight.is_simulator && <span className="rounded-full border border-line px-2.5 py-0.5 text-stone">Simulator</span>}
                {flight.aircraft && (
                    <Link href={`/aircraft/${flight.aircraft}`} className="rounded-full border border-line px-2.5 py-0.5 text-fern hover:border-ash">
                        View {flight.registration_number} in your fleet
                    </Link>
                )}
            </div>

            {mapData && (
                <div className="mt-8 animate-rise">
                    <RouteMap data={mapData} className="h-72" />
                </div>
            )}

            <div className="grid gap-x-10 md:grid-cols-2">
                <Section title="Logbook columns">
                    {columns.length === 0 && counts.length === 0 ? (
                        <p className="text-sm text-ash">No time breakdown logged. <Link href={`/flights/${flight.id}/edit`} className="text-fern hover:underline">Add one</Link>.</p>
                    ) : (
                        <dl className="grid grid-cols-2 gap-4 text-sm">
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
                    )}
                </Section>

                <Section title="Route & gates">
                    <dl className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <dt className="eyebrow">Departure gate</dt>
                            <dd className="mt-1 text-bone">{flight.departure_gate || '—'}</dd>
                        </div>
                        <div>
                            <dt className="eyebrow">Arrival gate</dt>
                            <dd className="mt-1 text-bone">{flight.arrival_gate || '—'}</dd>
                        </div>
                        <div className="col-span-2">
                            <dt className="eyebrow">Flight plan</dt>
                            <dd className="mt-1 break-words font-mono text-bone">{flight.flight_plan || '—'}</dd>
                        </div>
                    </dl>
                </Section>
            </div>

            {(flight.signature || durationToSeconds(flight.dual_received_time) > 0) && (
                <Section title="Instructor sign-off">
                    {flight.signature ? (
                        <SignatureDetails signature={flight.signature} viewer="student" />
                    ) : (
                        <p className="text-sm text-ash">
                            Not signed yet. <Link href="/instruction" className="text-fern hover:underline">Link your instructor</Link> and
                            they can sign this lesson from their account.
                        </p>
                    )}
                    <p className="mt-3 text-xs text-ash">{DISCLAIMER}</p>
                </Section>
            )}

            {flight.weather_conditions && (
                <Section title="Weather">
                    <p className="break-words rounded-lg border border-line bg-graphite/50 px-4 py-3 font-mono text-sm text-stone">{flight.weather_conditions}</p>
                </Section>
            )}

            {flight.notes && (
                <Section title="Notes">
                    <p className="whitespace-pre-line text-bone">{flight.notes}</p>
                </Section>
            )}

            {flight.photo && (
                <Section title="Photo">
                    <div className="relative aspect-[16/9] overflow-hidden rounded-xl border border-line">
                        <Image
                            src={photoUrl(flight.photo)}
                            alt={`Photo from ${flight.departure_airport} to ${flight.arrival_airport}`}
                            fill
                            sizes="(min-width: 1024px) 960px, 100vw"
                            unoptimized
                            className="object-cover"
                        />
                    </div>
                </Section>
            )}
        </PageShell>
    );
}
