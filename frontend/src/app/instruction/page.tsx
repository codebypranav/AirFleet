"use client";

import { useState } from 'react';
import Link from 'next/link';
import { CheckIcon } from '@/components/Icons';
import { EmptyState, ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import { ENDORSEMENT_NOTE, EndorsementCard } from '@/components/Endorsements';
import { DISCLAIMER } from '@/components/Signature';
import type { InstructorLink } from '@/types/flight';
import { acceptLink, endLink, getInstructorLinks, getMyEndorsements, getProfile, inviteToLink } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

function InviteForm({ canInstruct, onInvited }: { canInstruct: boolean; onInvited: () => void }) {
    const [invitee, setInvitee] = useState('');
    const [role, setRole] = useState<'instructor' | 'student'>('instructor');
    const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);
    const [sending, setSending] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSending(true);
        setStatus(null);
        try {
            const link = await inviteToLink(invitee.trim(), role);
            setInvitee('');
            setStatus({ ok: true, message: `Invitation sent to ${link.other.username}. They'll see it here when they sign in.` });
            onInvited();
        } catch (err) {
            setStatus({ ok: false, message: err instanceof Error ? err.message : 'Could not send the invitation' });
        } finally {
            setSending(false);
        }
    };

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {status && (
                <p className={status.ok ? 'flex items-center gap-2 text-sm text-fern' : 'alert-error'} role={status.ok ? 'status' : 'alert'}>
                    {status.ok && <CheckIcon className="h-4 w-4" />}
                    {status.message}
                </p>
            )}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_auto]">
                <div>
                    <label htmlFor="invitee" className="field-label">Username or email</label>
                    <input id="invitee" value={invitee} onChange={(e) => setInvitee(e.target.value)} required autoComplete="off" className="field-input" />
                </div>
                <div>
                    <label htmlFor="invitee_role" className="field-label">Invite them as</label>
                    <select id="invitee_role" value={role} onChange={(e) => setRole(e.target.value as 'instructor' | 'student')} className="field-input">
                        <option value="instructor">My instructor</option>
                        <option value="student">My student</option>
                    </select>
                </div>
            </div>
            {role === 'student' && !canInstruct && (
                <p className="text-xs text-ash">
                    Add your instructor certificate on your <Link href="/profile" className="text-fern hover:underline">profile</Link> first.
                </p>
            )}
            <div className="flex justify-end">
                <button type="submit" className="btn btn-primary" disabled={sending || !invitee.trim()}>
                    {sending ? 'Sending…' : 'Send invitation'}
                </button>
            </div>
        </form>
    );
}

function LinkRow({ link, onChange }: { link: InstructorLink; onChange: () => void }) {
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const act = async (action: () => Promise<unknown>) => {
        setBusy(true);
        setError('');
        try {
            await action();
            onChange();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
            setBusy(false);
        }
    };
    const end = () => {
        const what = link.status === 'PENDING'
            ? (link.awaiting_my_response ? 'Decline this invitation?' : 'Withdraw this invitation?')
            : `Stop being linked with ${link.other.username}? Lessons already signed stay signed.`;
        if (window.confirm(what)) act(() => endLink(link.id));
    };

    const pending = link.status === 'PENDING';
    return (
        <li className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <p className="text-bone">
                    {link.other.name}
                    {link.other.name !== link.other.username && <span className="text-ash"> · {link.other.username}</span>}
                </p>
                <p className="mt-1 text-xs text-ash">
                    {link.role === 'student' ? 'Your instructor' : 'Your student'}
                    {link.other.certificate_number && <> · certificate <span className="font-mono">{link.other.certificate_number}</span></>}
                    {' · '}
                    {pending
                        ? (link.awaiting_my_response ? 'invited you' : 'invitation sent') + ` ${formatDate(link.created_at)}`
                        : `linked since ${formatDate(link.accepted_at ?? link.created_at)}`}
                </p>
                {error && <p className="alert-error mt-3" role="alert">{error}</p>}
            </div>
            <div className="flex flex-wrap gap-2">
                {link.role === 'instructor' && !pending && (
                    <Link href={`/instruction/students/${link.id}`} className="btn btn-primary">
                        {link.unsigned_flights ? `${link.unsigned_flights} to sign` : 'Lessons'}
                    </Link>
                )}
                {link.awaiting_my_response && (
                    <button onClick={() => act(() => acceptLink(link.id))} disabled={busy} className="btn btn-primary">Accept</button>
                )}
                <button onClick={end} disabled={busy} className="btn btn-ghost">
                    {pending ? (link.awaiting_my_response ? 'Decline' : 'Withdraw') : 'Unlink'}
                </button>
            </div>
        </li>
    );
}

export default function InstructionPage() {
    const { data: links, error, reload } = useApi(getInstructorLinks);
    const { data: profile } = useApi(getProfile);
    const { data: endorsements } = useApi(getMyEndorsements);

    const invitations = links?.filter((l) => l.awaiting_my_response) ?? [];
    const instructors = links?.filter((l) => l.role === 'student' && !l.awaiting_my_response) ?? [];
    const students = links?.filter((l) => l.role === 'instructor' && !l.awaiting_my_response) ?? [];
    const group = (title: string, items: InstructorLink[]) => items.length > 0 && (
        <Section title={title}>
            <ul className="space-y-3">
                {items.map((link) => <LinkRow key={link.id} link={link} onChange={reload} />)}
            </ul>
        </Section>
    );

    return (
        <PageShell>
            <PageHeader
                eyebrow="Instruction"
                title="Instructors & students"
                description="Link with your instructor and they can sign the lessons in your logbook. If you instruct, your students can link with you too."
            />
            <InviteForm canInstruct={Boolean(profile?.instructor_certificate_number)} onInvited={reload} />

            {error ? (
                <div className="mt-8"><ErrorState message={error} onRetry={reload} /></div>
            ) : !links ? (
                <Spinner label="Finding your instructors" />
            ) : links.length === 0 ? (
                <div className="mt-8">
                    <EmptyState title="Nobody linked yet">
                        <p>
                            Invite your instructor by their AirFleet username or email. Once they accept, they can see the
                            logbook entries of flights where you logged dual received, and sign them.
                        </p>
                    </EmptyState>
                </div>
            ) : (
                <>
                    {group('Invitations for you', invitations)}
                    {group('My instructors', instructors)}
                    {group('My students', students)}
                </>
            )}

            {endorsements && endorsements.length > 0 && (
                <Section title="My endorsements">
                    <ul className="space-y-3">
                        {endorsements.map((e) => <EndorsementCard key={e.id} endorsement={e} />)}
                    </ul>
                    <p className="mt-3 text-xs text-ash">{ENDORSEMENT_NOTE}</p>
                </Section>
            )}

            <p className="mt-12 text-xs text-ash">{DISCLAIMER}</p>
        </PageShell>
    );
}
