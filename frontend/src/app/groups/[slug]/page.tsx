"use client";

import { use, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CREATABLE_KINDS, KIND_LABELS } from '@/components/GroupBadges';
import { EmptyState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import type { GroupDetail, GroupKind, GroupMember } from '@/types/flight';
import { deleteGroup, getGroup, joinGroup, removeMember, updateGroup, updateMember } from '@/utils/api';
import { useApi } from '@/utils/useApi';

const CONTACT = process.env.NEXT_PUBLIC_PRIVACY_CONTACT;

function EditGroupForm({ group, onSaved }: { group: GroupDetail; onSaved: (group: GroupDetail) => void }) {
    const router = useRouter();
    const [name, setName] = useState(group.name);
    const [kind, setKind] = useState<GroupKind>(group.kind);
    const [description, setDescription] = useState(group.description);
    const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);

    const save = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus(null);
        try {
            onSaved(await updateGroup(group.slug, { name: name.trim(), kind, description }));
            setStatus({ ok: true, message: 'Group saved.' });
        } catch (err) {
            setStatus({ ok: false, message: err instanceof Error ? err.message : 'Could not save the group' });
        }
    };
    const remove = async () => {
        if (!window.confirm(`Delete ${group.name}? Its members lose the badge.`)) return;
        try {
            await deleteGroup(group.slug);
            router.push('/groups');
        } catch (err) {
            setStatus({ ok: false, message: err instanceof Error ? err.message : 'Could not delete the group' });
        }
    };

    return (
        <form onSubmit={save} className="card space-y-5 p-5 sm:p-6">
            {status && <p className={status.ok ? 'text-sm text-fern' : 'alert-error'} role={status.ok ? 'status' : 'alert'}>{status.message}</p>}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_auto]">
                <div>
                    <label htmlFor="edit_name" className="field-label">Group name</label>
                    <input id="edit_name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} disabled={group.is_official} className="field-input" />
                </div>
                <div>
                    <label htmlFor="edit_kind" className="field-label">Kind</label>
                    <select id="edit_kind" value={kind} onChange={(e) => setKind(e.target.value as GroupKind)} disabled={group.is_official} className="field-input">
                        {CREATABLE_KINDS.map((k) => (
                            <option key={k} value={k}>{KIND_LABELS[k]}</option>
                        ))}
                    </select>
                </div>
            </div>
            <div>
                <label htmlFor="edit_description" className="field-label">Description</label>
                <textarea id="edit_description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} className="field-input" />
            </div>
            {!group.is_official && CONTACT && (
                <p className="text-xs text-ash">
                    Represent this organization? Email <a href={`mailto:${CONTACT}`} className="text-fern hover:underline">{CONTACT}</a> to make the group official.
                </p>
            )}
            <div className="flex flex-wrap justify-end gap-2">
                {!group.is_official && <button type="button" onClick={remove} className="btn btn-ghost">Delete group</button>}
                <button type="submit" className="btn btn-primary">Save group</button>
            </div>
        </form>
    );
}

export default function GroupPage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = use(params);
    const { data: group, error, reload, setData } = useApi(() => getGroup(slug), slug);
    const [problem, setProblem] = useState('');
    const [busy, setBusy] = useState(false);

    const act = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setProblem('');
        try {
            await action();
            reload();
        } catch (err) {
            setProblem(err instanceof Error ? err.message : 'Something went wrong');
        } finally {
            setBusy(false);
        }
    };

    if (error) {
        return (
            <PageShell>
                <EmptyState title="No group here">
                    <p>This group doesn&apos;t exist or was deleted. <Link href="/groups" className="text-fern hover:underline">Browse groups</Link>.</p>
                </EmptyState>
            </PageShell>
        );
    }
    if (!group) return <PageShell><Spinner label="Finding the group" /></PageShell>;

    const me = group.my_membership;
    const admin = me?.role === 'admin';
    const memberAction = (m: GroupMember) => admin && m.id !== me?.id && (
        <span className="flex gap-2">
            <button onClick={() => act(() => updateMember(slug, m.id, { role: m.role === 'admin' ? 'member' : 'admin' }))} disabled={busy} className="btn btn-ghost px-3 py-1 text-xs">
                {m.role === 'admin' ? 'Remove admin' : 'Make admin'}
            </button>
            {m.role !== 'admin' && (
                <button onClick={() => window.confirm(`Remove ${m.username} from the group?`) && act(() => removeMember(slug, m.id))} disabled={busy} className="btn btn-ghost px-3 py-1 text-xs">
                    Remove
                </button>
            )}
        </span>
    );

    return (
        <PageShell>
            <PageHeader
                eyebrow={`${KIND_LABELS[group.kind]} · ${group.is_official ? 'Official' : 'Community group'}`}
                title={group.name}
                description={group.description || undefined}
                action={
                    group.kind !== 'alliance' && (
                        !me ? (
                            <button onClick={() => act(() => joinGroup(slug))} disabled={busy} className="btn btn-primary">
                                {group.is_official ? 'Request to join' : 'Join group'}
                            </button>
                        ) : (
                            <button onClick={() => act(() => removeMember(slug, me.id))} disabled={busy} className="btn btn-ghost">
                                {me.status === 'pending' ? 'Cancel request' : 'Leave group'}
                            </button>
                        )
                    )
                }
            />
            {problem && <p className="alert-error mb-6" role="alert">{problem}</p>}
            {me?.status === 'pending' && <p className="mb-6 text-sm text-ash" role="status">Requested. A group admin will review it.</p>}
            {group.parent && (
                <p className="mb-6 text-sm text-ash">
                    Member of <Link href={`/groups/${group.parent.slug}`} className="text-fern hover:underline">{group.parent.name}</Link>
                </p>
            )}

            {group.kind === 'alliance' ? (
                <Section title="Member airlines">
                    {group.children.length === 0 ? (
                        <p className="text-sm text-ash">No member airlines yet.</p>
                    ) : (
                        <ul className="divide-y divide-line rounded-xl border border-line">
                            {group.children.map((c) => (
                                <li key={c.slug}>
                                    <Link href={`/groups/${c.slug}`} className="flex items-center justify-between gap-4 px-4 py-3 text-sm transition-colors hover:bg-graphite/50">
                                        <span className="text-bone">{c.name}</span>
                                        <span className="text-ash">{c.member_count.toLocaleString()} {c.member_count === 1 ? 'pilot' : 'pilots'}</span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    )}
                </Section>
            ) : (
                <Section title={`Members · ${group.member_count.toLocaleString()}`}>
                    <ul className="divide-y divide-line rounded-xl border border-line">
                        {group.members.map((m) => (
                            <li key={m.id} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
                                <span className="text-bone">
                                    {m.username}
                                    {m.role === 'admin' && <span className="text-ash"> · admin</span>}
                                </span>
                                {memberAction(m)}
                            </li>
                        ))}
                        {group.private_count > 0 && (
                            <li className="px-4 py-3 text-sm text-ash">
                                {group.members.length > 0 ? 'and ' : ''}{group.private_count} {group.private_count === 1 ? 'pilot' : 'pilots'} with a private profile
                            </li>
                        )}
                    </ul>
                </Section>
            )}

            {admin && group.pending.length > 0 && (
                <Section title="Requests to join">
                    <ul className="divide-y divide-line rounded-xl border border-line">
                        {group.pending.map((m) => (
                            <li key={m.id} className="flex flex-wrap items-center justify-between gap-4 px-4 py-3 text-sm">
                                <span className="text-bone">{m.username}</span>
                                <span className="flex gap-2">
                                    <button onClick={() => act(() => updateMember(slug, m.id, { status: 'active' }))} disabled={busy} className="btn btn-primary px-3 py-1 text-xs">Approve</button>
                                    <button onClick={() => act(() => removeMember(slug, m.id))} disabled={busy} className="btn btn-ghost px-3 py-1 text-xs">Decline</button>
                                </span>
                            </li>
                        ))}
                    </ul>
                </Section>
            )}

            {admin && (
                <Section title="Manage group">
                    <EditGroupForm key={group.slug} group={group} onSaved={(saved) => setData(() => saved)} />
                </Section>
            )}
        </PageShell>
    );
}
