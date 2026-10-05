"use client";

import { useState, useEffect } from 'react';
import { PageShell, PageHeader, EmptyState, Spinner } from '@/components/PageShell';
import { durationToSeconds, formatDuration } from '@/utils/format';

// Use environment variable with fallback
const BASE_URL = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`;

interface Ranking {
    username: string;
    total_flights?: number;
    total_time?: string;
    total_distance?: number;
}

interface RankingsData {
    flights: Ranking[];
    time: Ranking[];
    distance: Ranking[];
}

const TABS = [
    { id: 'flights', label: 'Total flights' },
    { id: 'time', label: 'Flight time' },
    { id: 'distance', label: 'Distance flown' },
] as const;

// Gold, silver and bronze, recast in the earth palette.
const PODIUM = ['text-fern', 'text-sand', 'text-clay'];

export default function RankingsPage() {
    const [rankings, setRankings] = useState<RankingsData | null>(null);
    const [activeTab, setActiveTab] = useState<'flights' | 'time' | 'distance'>('flights');

    useEffect(() => {
        const fetchRankings = async () => {
            try {
                const response = await fetch(`${BASE_URL}/rankings/`);
                if (!response.ok) throw new Error('Failed to fetch rankings');
                const data = await response.json();
                setRankings(data);
            } catch (error) {
                console.error('Error fetching rankings:', error);
            }
        };

        fetchRankings();
    }, []);

    const metric = (rank: Ranking) => {
        if (activeTab === 'flights') return rank.total_flights ?? 0;
        if (activeTab === 'time') return durationToSeconds(rank.total_time);
        return Number(rank.total_distance) || 0;
    };

    const display = (rank: Ranking) => {
        if (activeTab === 'flights') return `${rank.total_flights ?? 0}`;
        if (activeTab === 'time') return formatDuration(rank.total_time);
        return `${(Number(rank.total_distance) || 0).toLocaleString()} nm`;
    };

    const renderRankings = () => {
        if (!rankings) return <Spinner label="Tallying the field" />;

        const data = rankings[activeTab];
        if (data.length === 0) {
            return <EmptyState title="No pilots ranked yet">Log a flight to put your name on the board.</EmptyState>;
        }
        const max = Math.max(...data.map(metric), 1);
        
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
                                <span className="truncate text-lg text-paper">{rank.username}</span>
                                <span className="shrink-0 font-mono text-sm text-bone">{display(rank)}</span>
                            </div>
                            <div className="mt-2 h-1 overflow-hidden rounded-full bg-graphite">
                                <div
                                    className={`h-full rounded-full transition-[width] duration-700 ${index === 0 ? 'bg-moss' : 'bg-ash/50'}`}
                                    style={{ width: `${(metric(rank) / max) * 100}%` }}
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
            <PageHeader
                eyebrow="Rankings"
                title="Pilot rankings"
                description="Who has been up there the most."
            />

            <div role="tablist" aria-label="Ranking metric" className="mb-8 inline-flex flex-wrap gap-1 rounded-full border border-line bg-char p-1">
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        role="tab"
                        aria-selected={activeTab === tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
                            activeTab === tab.id
                                ? 'bg-bone text-ink'
                                : 'text-ash hover:text-bone'
                        }`}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {renderRankings()}
        </PageShell>
    );
}
