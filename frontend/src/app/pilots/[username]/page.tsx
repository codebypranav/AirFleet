"use client";

import { use } from 'react';
import Link from 'next/link';
import RouteMap from '@/components/RouteMap';
import { AchievementGrid } from '@/components/Insights';
import { PlaneIcon } from '@/components/Icons';
import { EmptyState, PageHeader, PageShell, Section, Spinner, StatGrid } from '@/components/PageShell';
import { getPublicPilot } from '@/utils/api';
import { formatDate, formatDuration } from '@/utils/format';
import { useApi } from '@/utils/useApi';

export default function PilotPage({ params }: { params: Promise<{ username: string }> }) {
    const { username } = use(params);
    const name = decodeURIComponent(username);
    const { data: pilot, error } = useApi(() => getPublicPilot(name), name);

    return (
        <PageShell variant="public">
            {error ? (
                <EmptyState title="No public logbook here">
                    <p>This pilot doesn&apos;t exist or keeps their logbook private.</p>
                </EmptyState>
            ) : !pilot ? (
                <Spinner label="Finding the pilot" />
            ) : (
                <>
                    <PageHeader
                        eyebrow={`Pilot${pilot.home_airport ? ` · based at ${pilot.home_airport}` : ''} · since ${formatDate(pilot.member_since, 'long')}`}
                        title={pilot.username}
                        description={pilot.bio || undefined}
                    />
                    <StatGrid
                        stats={[
                            { label: 'Total time', value: `${pilot.stats.hours.toLocaleString()} h` },
                            { label: 'Flights', value: pilot.stats.flights.toLocaleString() },
                            { label: 'Distance', value: `${pilot.stats.distance.toLocaleString()} nm` },
                            { label: 'Airports', value: pilot.stats.airports.toLocaleString() },
                        ]}
                    />

                    <Section title="Where they've flown">
                        <RouteMap data={pilot.routes} className="h-96" />
                    </Section>

                    {pilot.achievements.length > 0 && (
                        <Section title="Achievements">
                            <AchievementGrid items={pilot.achievements} />
                        </Section>
                    )}

                    <Section title="Recent flights">
                        {pilot.recent_flights.length === 0 ? (
                            <p className="text-sm text-ash">No flights yet.</p>
                        ) : (
                            <ul className="divide-y divide-line rounded-xl border border-line">
                                {pilot.recent_flights.map((f) => (
                                    <li key={f.id}>
                                        <Link href={`/share/flights/${f.id}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 text-sm transition-colors hover:bg-graphite/50">
                                            <span className="flex items-center gap-2 font-mono text-bone">
                                                {f.departure_airport}
                                                <PlaneIcon className="h-3.5 w-3.5 rotate-90 text-moss" />
                                                {f.arrival_airport}
                                            </span>
                                            <span className="text-ash">{formatDate(f.departure_time)}</span>
                                            <span className="font-mono text-stone">{formatDuration(f.total_time)} · {f.distance.toLocaleString()} nm</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </Section>
                </>
            )}
        </PageShell>
    );
}
