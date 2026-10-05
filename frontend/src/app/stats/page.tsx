"use client";

import Link from 'next/link';
import RouteMap from '@/components/RouteMap';
import { AchievementGrid, CurrencyCards, MonthlyHoursChart, RankedList } from '@/components/Insights';
import { EmptyState, ErrorState, PageHeader, PageShell, Section, Spinner, StatGrid } from '@/components/PageShell';
import { getAchievements, getCurrency, getRoutes, getStats } from '@/utils/api';
import { useApi } from '@/utils/useApi';

export default function StatsPage() {
    const stats = useApi(() => getStats());
    const currency = useApi(getCurrency);
    const achievements = useApi(getAchievements);
    const routes = useApi(getRoutes);

    const totals = stats.data?.totals;
    const earned = achievements.data?.filter((a) => a.earned).length ?? 0;

    return (
        <PageShell>
            <PageHeader eyebrow="Stats" title="Your flying" description="Totals, trends, currency and the places you've been." />

            {stats.error ? (
                <ErrorState message={stats.error} onRetry={stats.reload} />
            ) : !stats.data || !totals ? (
                <Spinner label="Adding up the columns" />
            ) : totals.flights === 0 ? (
                <EmptyState title="Nothing to count yet">
                    <p>Log a few flights and your totals, currency and route map will appear here.</p>
                    <Link href="/flights/add" className="btn btn-primary mt-6">Log a flight</Link>
                </EmptyState>
            ) : (
                <>
                    <StatGrid
                        stats={[
                            { label: 'Total time', value: `${totals.hours.toLocaleString()} h` },
                            { label: 'Flights', value: totals.flights.toLocaleString() },
                            { label: 'Distance', value: `${totals.distance.toLocaleString()} nm` },
                            { label: 'Airports', value: `${totals.airports} · ${totals.countries} ${totals.countries === 1 ? 'country' : 'countries'}` },
                        ]}
                    />
                    <div className="mt-px">
                        <StatGrid
                            stats={[
                                { label: 'PIC', value: `${totals.pic_hours} h` },
                                { label: 'Night', value: `${totals.night_hours} h` },
                                { label: 'Instrument', value: `${totals.instrument_hours} h` },
                                { label: 'Landings', value: totals.landings.toLocaleString() },
                            ]}
                        />
                    </div>

                    <Section title="Currency">
                        {currency.data ? <CurrencyCards items={currency.data} /> : <p className="text-sm text-ash">Checking…</p>}
                    </Section>

                    <Section title="Monthly hours">
                        <div className="card p-5 sm:p-6">
                            <MonthlyHoursChart months={stats.data.by_month} />
                        </div>
                    </Section>

                    <Section title="Route map">
                        {routes.data ? <RouteMap data={routes.data} className="h-96" /> : <div className="card h-96" />}
                    </Section>

                    <div className="grid gap-x-10 md:grid-cols-2">
                        <Section title="Most flown routes">
                            <RankedList
                                empty="No routes yet."
                                rows={stats.data.top_routes.map((r) => ({
                                    key: `${r.from}-${r.to}`,
                                    label: <span className="font-mono">{r.from} → {r.to}</span>,
                                    detail: `${r.flights}× · ${r.hours} h`,
                                    value: r.flights,
                                }))}
                            />
                        </Section>
                        <Section title="Most flown aircraft">
                            <RankedList
                                empty="No aircraft yet."
                                rows={stats.data.top_aircraft.map((a) => ({
                                    key: a.registration,
                                    label: <span className="font-mono">{a.registration}{a.type_code && <span className="text-ash"> · {a.type_code}</span>}</span>,
                                    detail: `${a.hours} h`,
                                    value: a.hours,
                                }))}
                            />
                        </Section>
                    </div>

                    <Section title={`Achievements${achievements.data ? ` · ${earned} of ${achievements.data.length}` : ''}`}>
                        {achievements.data ? <AchievementGrid items={achievements.data} /> : <p className="text-sm text-ash">Loading…</p>}
                    </Section>
                </>
            )}
        </PageShell>
    );
}
