"use client";

import Link from 'next/link';
import { EmptyState, ErrorState, PageHeader, PageShell, Spinner } from '@/components/PageShell';
import type { AppNotification } from '@/types/flight';
import { getNotifications } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

const WHAT = {
    follow_request: 'asked to follow you',
    follow: 'started following you',
    approved: 'approved your follow request',
    comment: 'commented on',
    reply: 'replied to your comment on',
    flight_like: 'liked',
    comment_like: 'liked your comment on',
} satisfies Record<AppNotification['kind'], string>;

function link(n: AppNotification) {
    if (!n.flight) return n.kind === 'follow_request' || n.kind === 'follow' ? '/profile' : '/following';
    return n.flight.mine ? `/flights/${n.flight.id}` : `/following?flight=${n.flight.id}`;
}

export default function NotificationsPage() {
    const { data, error, reload } = useApi(getNotifications, 'notifications');

    return (
        <PageShell>
            <PageHeader eyebrow="Notifications" title="What's new" description="Follows, comments and likes from the last 90 days." />
            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !data ? (
                <Spinner label="Fetching notifications" />
            ) : data.length === 0 ? (
                <EmptyState title="Nothing new">Follows, comments and likes on your flights show up here.</EmptyState>
            ) : (
                <ul className="divide-y divide-line rounded-xl border border-line">
                    {data.map((n) => (
                        <li key={n.id}>
                            <Link href={link(n)} className="flex items-start justify-between gap-4 px-4 py-3 transition-colors hover:bg-graphite/50">
                                <p className="text-sm text-bone">
                                    {!n.read && <span className="mr-2 inline-block h-2 w-2 rounded-full bg-clay" aria-label="New" />}
                                    <span className="text-paper">{n.actor}</span> {WHAT[n.kind]}
                                    {n.flight && <> {n.flight.mine ? 'your flight' : 'a flight'} <span className="font-mono">{n.flight.route}</span></>}
                                </p>
                                <span className="shrink-0 text-xs text-ash">{formatDate(n.created_at)}</span>
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </PageShell>
    );
}
