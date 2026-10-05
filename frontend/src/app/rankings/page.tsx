"use client";

import { useState } from 'react';
import Link from 'next/link';
import { PageShell, PageHeader, EmptyState, ErrorState, Spinner } from '@/components/PageShell';
import { apiJson } from '@/utils/api';
import { durationToSeconds, formatDuration } from '@/utils/format';
import { useApi } from '@/utils/useApi';

interface Ranking {
    username: string;
    is_public: boolean;
    total_flights?: number;
    total_time?: string;
    total_distance?: number;
    longest_flight?: string;
    airports_visited?: number;
}

type Metric = 'flights' | 'time' | 'distance' | 'longest' | 'airports';
type Period = 'all' | 'year' | 'month';
type RankingsData = Record<Metric, Ranking[]> & { period: Period };

const TABS: { id: Metric; label: string }[] = [
    { id: 'flights', label: 'Total flights' },
    { id: 'time', label: 'Flight time' },
    { id: 'distance', label: 'Distance flown' },
    { id: 'longest', label: 'Longest flight' },
    { id: 'airports', label: 'Airports visited' },
];

const PERIODS: { id: Period; label: string }[] = [
    { id: 'all', label: 'All time' },
    { id: 'year', label: 'This year' },
    { id: 'month', label: 'This month' },
];

// Gold, silver and bronze, recast in the earth palette.
const PODIUM = ['text-fern', 'text-sand', 'text-clay'];

const metric = (tab: Metric, rank: Ranking) => {
    switch (tab) {
        case 'flights': return rank.total_flights ?? 0;
        case 'time': return durationToSeconds(rank.total_time);
        case 'distance': return Number(rank.total_distance) || 0;
        case 'longest': return durationToSeconds(rank.longest_flight);
        case 'airports': return rank.airports_visited ?? 0;
    }
};

const display = (tab: Metric, rank: Ranking) => {
    switch (tab) {
        case 'flights': return `${rank.total_flights ?? 0}`;
        case 'time': return formatDuration(rank.total_time);
        case 'distance': return `${(Number(rank.total_distance) || 0).toLocaleString()} nm`;
        case 'longest': return formatDuration(rank.longest_flight);
        case 'airports': return `${rank.airports_visited ?? 0}`;
    }
};

function Tabs<T extends string>({ label, options, value, onChange }: { label: string; options: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
    return (
        <div role="tablist" aria-label={label} className="inline-flex flex-wrap gap-1 rounded-full border border-line bg-char p-1">
            {options.map((option) => (
                <button
                    key={option.id}
                    role="tab"
                    aria-selected={value === option.id}
                    onClick={() => onChange(option.id)}
                    className={`rounded-full px-4 py-1.5 text-sm transition-colors ${value === option.id ? 'bg-bone text-ink' : 'text-ash hover:text-bone'}`}
                >
                    {option.label}
                </button>
            ))}
        </div>
    );
}

export default function RankingsPage() {
    const [activeTab, setActiveTab] = useState<Metric>('flights');
    const [period, setPeriod] = useState<Period>('all');
    const { data: rankings, error, reload } = useApi(
        () => apiJson<RankingsData>(`/rankings/?period=${period}`, { auth: false }),
        period,
    );

    const renderRankings = () => {
        if (error) return <ErrorState message={error} onRetry={reload} />;
        if (!rankings || rankings.period !== period) return <Spinner label="Tallying the field" />;

        const data = rankings[activeTab];
        if (data.length === 0) {
            return <EmptyState title="No pilots ranked yet">Log a flight to put your name on the board.</EmptyState>;
        }
        const max = Math.max(...data.map((r) => metric(activeTab, r)), 1);

        return (
            <ol className="space-y-2.5">
                {data.map((rank, index) => (
                    <li
                        key={rank.username}
                        className="card flex items-center gap-4 overflow-hidden px-4 py-3.5 sm:gap-6 sm:px-6 animate-rise"
                        style={{ animationDelay: `${Math.min(index, 10) * 40}ms` }}
                    >
                        <span className={`w-10 shrink-0 font-display text-3xl font-light tabular-nums ${PODIUM[index] ?? 'text-ash/60'}`}>
                            {String(index + 1).padStart(2, '0')}
                        </span>
                        <div className="min-w-0 flex-1">
                            <div className="flex items-baseline justify-between gap-4">
                                {rank.is_public ? (
                                    <Link href={`/pilots/${encodeURIComponent(rank.username)}`} className="truncate text-lg text-paper underline-offset-4 hover:text-fern hover:underline">
                                        {rank.username}
                                    </Link>
                                ) : (
                                    <span className="truncate text-lg text-paper">{rank.username}</span>
                                )}
                                <span className="shrink-0 font-mono text-sm text-bone">{display(activeTab, rank)}</span>
                            </div>
                            <div className="mt-2 h-1 overflow-hidden rounded-full bg-graphite">
                                <div
                                    className={`h-full rounded-full transition-[width] duration-700 ${index === 0 ? 'bg-moss' : 'bg-ash/50'}`}
                                    style={{ width: `${(metric(activeTab, rank) / max) * 100}%` }}
                                />
                            </div>
                        </div>
                    </li>
                ))}
            </ol>
        );
    };

    return (
        <PageShell>
            <PageHeader eyebrow="Rankings" title="Pilot rankings" description="Who has been up there the most." />
            <div className="mb-8 flex flex-col gap-3">
                <Tabs label="Period" options={PERIODS} value={period} onChange={setPeriod} />
                <Tabs label="Ranking metric" options={TABS} value={activeTab} onChange={setActiveTab} />
            </div>
            {renderRankings()}
        </PageShell>
    );
}
