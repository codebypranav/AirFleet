"use client";

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CREATABLE_KINDS, KIND_LABELS } from '@/components/GroupBadges';
import { CheckIcon } from '@/components/Icons';
import { EmptyState, ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import type { Group, GroupKind } from '@/types/flight';
import { createGroup, getGroups } from '@/utils/api';
import { useApi } from '@/utils/useApi';

function tally(group: Group) {
    const n = group.kind === 'alliance' ? group.child_count : group.member_count;
    const noun = group.kind === 'alliance' ? 'airline' : 'member';
    return `${n.toLocaleString()} ${n === 1 ? noun : `${noun}s`}`;
}

function GroupList({ groups }: { groups: Group[] }) {
    return (
        <ul className="divide-y divide-line rounded-xl border border-line">
            {groups.map((g) => (
                <li key={g.slug}>
                    <Link href={`/groups/${g.slug}`} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 text-sm transition-colors hover:bg-graphite/50">
                        <span className="flex items-center gap-2 text-bone">
                            {g.is_official && <CheckIcon className="h-3.5 w-3.5 text-fern" />}
                            {g.name}
                        </span>
                        <span className="text-ash">
                            {KIND_LABELS[g.kind]} · {g.is_official ? 'Official' : 'Community group'} · {tally(g)}
                            {g.my_membership?.status === 'pending' && ' · Requested'}
                        </span>
                    </Link>
                </li>
            ))}
        </ul>
    );
}

function CreateGroupForm() {
    const router = useRouter();
    const [name, setName] = useState('');
    const [kind, setKind] = useState<GroupKind>('community');
    const [description, setDescription] = useState('');
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            const group = await createGroup({ name: name.trim(), kind, description });
            router.push(`/groups/${group.slug}`);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not create the group');
            setSaving(false);
        }
    };

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_auto]">
                <div>
                    <label htmlFor="group_name" className="field-label">Group name</label>
                    <input id="group_name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} className="field-input" />
                </div>
                <div>
                    <label htmlFor="group_kind" className="field-label">Kind</label>
                    <select id="group_kind" value={kind} onChange={(e) => setKind(e.target.value as GroupKind)} className="field-input">
                        {CREATABLE_KINDS.map((k) => (
                            <option key={k} value={k}>{KIND_LABELS[k]}</option>
                        ))}
                    </select>
                </div>
            </div>
            <div>
                <label htmlFor="group_description" className="field-label">Description</label>
                <textarea id="group_description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} className="field-input" />
            </div>
            <p className="text-xs text-ash">You can start up to 5 groups. New groups show as community groups until AirFleet makes them official.</p>
            <div className="flex justify-end">
                <button type="submit" className="btn btn-primary" disabled={saving || !name.trim()}>
                    {saving ? 'Creating…' : 'Create group'}
                </button>
            </div>
        </form>
    );
}

export default function GroupsPage() {
    const [search, setSearch] = useState('');
    const [q, setQ] = useState('');
    const mine = useApi(() => getGroups({ mine: '1' }), 'mine');
    const found = useApi(() => getGroups({ q }), q);

    return (
        <PageShell>
            <PageHeader
                eyebrow="Groups"
                title="Groups"
                description="Airlines, operators, flight schools, alliances and clubs. Join the ones you fly with."
            />

            <Section title="Your groups">
                {mine.error ? (
                    <ErrorState message={mine.error} onRetry={mine.reload} />
                ) : !mine.data ? (
                    <Spinner label="Finding your groups" />
                ) : mine.data.length === 0 ? (
                    <p className="text-sm text-ash">You&apos;re not in any groups yet.</p>
                ) : (
                    <GroupList groups={mine.data} />
                )}
            </Section>

            <Section title="Find a group">
                <form onSubmit={(e) => { e.preventDefault(); setQ(search.trim()); }} className="mb-4 flex gap-2">
                    <label htmlFor="group_search" className="sr-only">Search groups</label>
                    <input id="group_search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Delta, Wheels Up, Star Alliance…" className="field-input" />
                    <button type="submit" className="btn btn-ghost">Search</button>
                </form>
                {found.error ? (
                    <ErrorState message={found.error} onRetry={found.reload} />
                ) : !found.data ? (
                    <Spinner label="Searching" />
                ) : found.data.length === 0 ? (
                    <EmptyState title="No groups found">
                        <p>Nobody has started that group yet. You can start it below.</p>
                    </EmptyState>
                ) : (
                    <GroupList groups={found.data} />
                )}
            </Section>

            <Section title="Start a group">
                <CreateGroupForm />
            </Section>
        </PageShell>
    );
}
