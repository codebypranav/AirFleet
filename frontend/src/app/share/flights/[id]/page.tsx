"use client";

import { use } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import RouteMap from '@/components/RouteMap';
import { EmptyState, PageHeader, PageShell, Section, Spinner, StatGrid } from '@/components/PageShell';
import { getPublicFlight } from '@/utils/api';
import { formatDate, formatDuration, formatTime, photoUrl } from '@/utils/format';
import { useApi } from '@/utils/useApi';

export default function SharedFlightPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const { data: flight, error } = useApi(() => getPublicFlight(id), id);

    if (error) {
        return (
            <PageShell variant="public">
                <EmptyState title="This flight isn't shared">
                    <p>It doesn&apos;t exist, or its pilot keeps their logbook private.</p>
                </EmptyState>
            </PageShell>
        );
    }
    if (!flight) {
        return <PageShell variant="public"><Spinner label="Opening the entry" /></PageShell>;
    }

    const mapData = flight.departure_info && flight.arrival_info
        ? {
            routes: [{ from: flight.departure_airport, to: flight.arrival_airport, flights: 1, hours: 0 }],
            airports: flight.departure_airport === flight.arrival_airport ? [flight.departure_info] : [flight.departure_info, flight.arrival_info],
        }
        : null;

    return (
        <PageShell variant="public">
            <PageHeader
                eyebrow={`${formatDate(flight.departure_time, 'long')}${flight.is_simulator ? ' · Simulator' : ''}`}
                title={`${flight.departure_airport} → ${flight.arrival_airport}`}
                description={[flight.departure_info?.name, flight.arrival_info?.name].filter(Boolean).join(' to ')}
                action={<Link href={`/pilots/${encodeURIComponent(flight.pilot)}`} className="btn btn-ghost">Flown by {flight.pilot}</Link>}
            />
            <StatGrid
                stats={[
                    { label: 'Block time', value: formatDuration(flight.total_time) },
                    { label: 'Distance', value: `${flight.distance.toLocaleString()} nm` },
                    { label: 'Aircraft', value: flight.registration_number + (flight.aircraft_type ? ` · ${flight.aircraft_type}` : '') },
                    { label: 'Off / On', value: `${formatTime(flight.departure_time)}–${formatTime(flight.arrival_time)}` },
                ]}
            />
            {mapData && (
                <div className="mt-8">
                    <RouteMap data={mapData} className="h-72" />
                </div>
            )}
            {flight.photo && (
                <Section title="Photo">
                    <div className="relative aspect-[16/9] overflow-hidden rounded-xl border border-line">
                        <Image src={photoUrl(flight.photo)} alt={`Photo from ${flight.departure_airport} to ${flight.arrival_airport}`} fill sizes="(min-width: 1024px) 960px, 100vw" unoptimized className="object-cover" />
                    </div>
                </Section>
            )}
        </PageShell>
    );
}
