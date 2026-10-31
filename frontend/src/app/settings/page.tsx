"use client";

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import { changePassword, clearTokens, deleteAccount, downloadExport, getProfile, saveTokens } from '@/utils/api';
import { useApi } from '@/utils/useApi';

function PasswordForm() {
    const [current, setCurrent] = useState('');
    const [next, setNext] = useState('');
    const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatus(null);
        try {
            saveTokens(await changePassword(current, next));
            setCurrent('');
            setNext('');
            setStatus({ ok: true, message: 'Password updated.' });
        } catch (err) {
            setStatus({ ok: false, message: err instanceof Error ? err.message : 'Could not change your password' });
        }
    };

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {status && <p className={status.ok ? 'text-sm text-fern' : 'alert-error'} role={status.ok ? 'status' : 'alert'}>{status.message}</p>}
            <input type="text" name="username" autoComplete="username" className="hidden" readOnly />
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div>
                    <label htmlFor="current_password" className="field-label">Current password</label>
                    <input id="current_password" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" className="field-input" />
                    <p className="mt-1.5 text-xs text-ash">Signed up with Google? <Link href="/forgot-password" className="text-fern hover:underline">Set a password by email</Link>.</p>
                </div>
                <div>
                    <label htmlFor="new_password" className="field-label">New password</label>
                    <input id="new_password" type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} autoComplete="new-password" className="field-input" />
                </div>
            </div>
            <div className="flex justify-end">
                <button type="submit" className="btn btn-ghost">Change password</button>
            </div>
        </form>
    );
}

function DeleteAccountForm({ username }: { username: string }) {
    const router = useRouter();
    const [confirm, setConfirm] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!window.confirm('Delete your account and every flight in it? This cannot be undone.')) return;
        setDeleting(true);
        setError(null);
        try {
            await deleteAccount(confirm.trim(), password);
            clearTokens();
            router.replace('/');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not delete your account');
            setDeleting(false);
        }
    };

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <p className="text-sm text-stone">
                Permanently deletes your profile, every flight, aircraft and photo. Public links stop working.
                You may want to <button type="button" onClick={() => downloadExport()} className="text-fern hover:underline">export your logbook</button> first.
                See the <Link href="/privacy" className="text-fern hover:underline">privacy notice</Link> for what we keep and where.
            </p>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div>
                    <label htmlFor="delete_confirm" className="field-label">Type <span className="font-mono">{username}</span> to confirm</label>
                    <input id="delete_confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="off" className="field-input" />
                </div>
                <div>
                    <label htmlFor="delete_password" className="field-label">Password</label>
                    <input id="delete_password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="field-input" />
                    <p className="mt-1.5 text-xs text-ash">Leave blank if you only sign in with Google.</p>
                </div>
            </div>
            <div className="flex justify-end">
                <button type="submit" className="btn btn-ghost text-rust" disabled={deleting || confirm.trim() !== username}>
                    {deleting ? 'Deleting…' : 'Delete account'}
                </button>
            </div>
        </form>
    );
}

export default function SettingsPage() {
    const { data: profile, error, reload } = useApi(getProfile);

    return (
        <PageShell>
            <PageHeader eyebrow="Settings" title="Account settings" />
            <Section title="Password">
                <PasswordForm />
            </Section>
            <Section title="Delete account">
                {error ? (
                    <ErrorState message={error} onRetry={reload} />
                ) : !profile ? (
                    <Spinner label="Finding your details" />
                ) : (
                    <DeleteAccountForm username={profile.username} />
                )}
            </Section>
        </PageShell>
    );
}
