"use client";

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useAction } from '@/components/Crew';
import { PilotList } from '@/components/Follow';
import { PlaneIcon } from '@/components/Icons';
import { Comments, LikeButton } from '@/components/Social';
import { EmptyState, ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import type { FeedFlight } from '@/types/flight';
import { followPilot, getFeed, getFeedEntry, getFollows, likeFlight, unfollowPilot } from '@/utils/api';
import { formatDate, formatDuration } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const PAGE_SIZE = 20;

function FeedRow({ flight, open = false }: { flight: FeedFlight; open?: boolean }) {
    const body = (
        <>
            <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                <span className="text-bone">{flight.pilot}</span>
                <span className="flex items-center gap-2 font-mono text-bone">
                    {flight.departure_airport}
                    <PlaneIcon className="h-3.5 w-3.5 rotate-90 text-moss" />
                    {flight.arrival_airport}
                </span>
                <span className="text-ash">{formatDate(flight.departure_time)}</span>
                <span className="font-mono text-stone">
                    {flight.registration_number}{flight.aircraft_type && ` · ${flight.aircraft_type}`} · {formatDuration(flight.total_time)} · {flight.distance.toLocaleString()} nm
                </span>
            </p>
            {flight.notes && <p className="mt-1 whitespace-pre-line text-sm text-ash">{flight.notes}</p>}
        </>
    );
    return (
        <li className="px-4 py-3">
            {flight.pilot_is_public ? (
                <Link href={`/share/flights/${flight.id}`} className="-mx-2 block rounded-lg px-2 py-1 transition-colors hover:bg-graphite/50">{body}</Link>
            ) : (
                <div className="py-1">{body}</div>
            )}
            <div className="mt-2 flex flex-col gap-1">
                <LikeButton liked={flight.liked} count={flight.like_count} toggle={(on) => likeFlight(flight.id, on)} />
                <Comments flightId={flight.id} count={flight.comment_count} startOpen={open} />
            </div>
        </li>
    );
}

function FeedEntry({ id }: { id: string }) {
    const { data: flight, error } = useApi(() => getFeedEntry(id), `entry-${id}`);
    if (error) return <ErrorState message={error} />;
    if (!flight) return <Spinner label="Fetching the flight" />;
    return (
        <ul className="rounded-xl border border-line">
            <FeedRow flight={flight} open />
        </ul>
    );
}

export default function FollowingPage() {
    return (
        <Suspense>
            <Following />
        </Suspense>
    );
}

function Following() {
    const entry = useSearchParams().get('flight');
    const [page, setPage] = useState(1);
    const feed = useApi(() => getFeed(page), `feed-${page}`);
    const { data: follows, reload } = useApi(getFollows, 'follows');
    const [username, setUsername] = useState('');
    const [sent, setSent] = useState('');
    const { busy, error, run } = useAction();
    const pages = Math.ceil((feed.data?.count ?? 0) / PAGE_SIZE);

    const follow = (e: React.FormEvent) => {
        e.preventDefault();
        run(() => followPilot(username.trim()).then((res) => {
            setSent(res.status === 'APPROVED' ? `You're following ${res.username}.` : `Request sent to ${res.username}.`);
            setUsername('');
            reload();
            feed.reload();
        }));
    };

    return (
        <PageShell>
            <PageHeader eyebrow="Following" title="Pilots you follow" description="Their flights in the air show at the top of every page, and their logged flights land here." />

            <Section title="Follow a pilot">
                <form onSubmit={follow} className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
                    <div>
                        <label htmlFor="follow-username" className="field-label">Username</label>
                        <input id="follow-username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Their AirFleet username" autoComplete="off" className="field-input" />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={busy || !username.trim()}>Follow</button>
                </form>
                {error && <p className="alert-error mt-3" role="alert">{error}</p>}
                {sent && !error && <p className="mt-3 text-sm text-fern" role="status">{sent}</p>}
                <p className="mt-3 text-xs text-ash">Public pilots are followed straight away. Private pilots get a request to approve.</p>
            </Section>

            {follows && (
                <Section title="Following">
                    <PilotList
                        pilots={follows.following}
                        actions={[['Unfollow', unfollowPilot]]}
                        note={(pilot) => (pilot.status === 'PENDING' ? 'Requested' : undefined)}
                        onDone={() => {
                            reload();
                            feed.reload();
                        }}
                        empty="You're not following anyone yet."
                    />
                </Section>
            )}

            {entry && (
                <Section title="Flight" action={<Link href="/following" className="text-xs text-ash hover:text-bone">All their flights</Link>}>
                    <FeedEntry id={entry} />
                </Section>
            )}

            <Section title="Their flights" className={entry ? 'hidden' : ''}>
                {feed.error ? (
                    <ErrorState message={feed.error} onRetry={feed.reload} />
                ) : !feed.data ? (
                    <Spinner label="Fetching their flights" />
                ) : feed.data.results.length === 0 ? (
                    <EmptyState title="Nothing logged yet">Flights logged by pilots you follow show up here.</EmptyState>
                ) : (
                    <>
                        <ul className="divide-y divide-line rounded-xl border border-line">
                            {feed.data.results.map((flight) => <FeedRow key={flight.id} flight={flight} />)}
                        </ul>
                        {pages > 1 && (
                            <nav className="mt-6 flex items-center justify-between gap-4" aria-label="Feed pages">
                                <button onClick={() => setPage((p) => p - 1)} disabled={page <= 1} className="btn btn-ghost">← Newer</button>
                                <span className="eyebrow">Page {page} of {pages}</span>
                                <button onClick={() => setPage((p) => p + 1)} disabled={page >= pages} className="btn btn-ghost">Older →</button>
                            </nav>
                        )}
                    </>
                )}
            </Section>
        </PageShell>
    );
}
