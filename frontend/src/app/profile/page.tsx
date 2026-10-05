"use client";

import { useState } from 'react';
import Link from 'next/link';
import { CheckIcon, ShareIcon } from '@/components/Icons';
import { ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import type { Profile } from '@/types/flight';
import { changePassword, getProfile, saveTokens, updateProfile } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

function ProfileForm({ profile, onSaved }: { profile: Profile; onSaved: (p: Profile) => void }) {
    const [form, setForm] = useState(profile);
    const [status, setStatus] = useState<{ ok: boolean; message: string } | null>(null);
    const [saving, setSaving] = useState(false);

    const change = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        const { name, value, type, checked } = e.target as HTMLInputElement;
        setForm((prev) => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    };

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setStatus(null);
        try {
            const saved = await updateProfile({
                username: form.username.trim(),
                email: form.email.trim(),
                first_name: form.first_name,
                last_name: form.last_name,
                bio: form.bio,
                home_airport: form.home_airport.trim().toUpperCase(),
                is_public: form.is_public,
            });
            setForm(saved);
            onSaved(saved);
            setStatus({ ok: true, message: 'Profile saved.' });
        } catch (err) {
            setStatus({ ok: false, message: err instanceof Error ? err.message : 'Could not save your profile' });
        } finally {
            setSaving(false);
        }
    };

    const input = (name: keyof Profile, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
        <div>
            <label htmlFor={name} className="field-label">{label}</label>
            <input id={name} name={name} value={String(form[name] ?? '')} onChange={change} className="field-input" {...props} />
        </div>
    );

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {status && <p className={status.ok ? 'flex items-center gap-2 text-sm text-fern' : 'alert-error'} role={status.ok ? 'status' : 'alert'}>{status.ok && <CheckIcon className="h-4 w-4" />}{status.message}</p>}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                {input('username', 'Username', { required: true, autoComplete: 'username' })}
                {input('email', 'Email', { type: 'email', required: true, autoComplete: 'email' })}
                {input('first_name', 'First name', { autoComplete: 'given-name' })}
                {input('last_name', 'Last name', { autoComplete: 'family-name' })}
                {input('home_airport', 'Home airport', { maxLength: 4, placeholder: 'e.g. KPAO', className: 'field-input font-mono uppercase' })}
            </div>
            <div>
                <label htmlFor="bio" className="field-label">About you</label>
                <textarea id="bio" name="bio" value={form.bio} onChange={change} rows={3} maxLength={500} className="field-input" placeholder="What you fly, where you're based, what you're working towards" />
            </div>
            <label htmlFor="is_public" className="flex cursor-pointer items-start gap-3 rounded-lg border border-line px-4 py-3 transition-colors hover:border-ash/60">
                <input type="checkbox" id="is_public" name="is_public" checked={form.is_public} onChange={change} className="mt-1 h-4 w-4 accent-[var(--color-moss)]" />
                <span>
                    <span className="block text-sm text-bone">Public profile</span>
                    <span className="block text-xs text-ash">
                        Anyone with the link can see your profile, totals, achievements, route map and flights
                        (route, times, aircraft, photo and story). Notes, gates and flight plans stay private.
                    </span>
                </span>
            </label>
            <div className="flex justify-end">
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save profile'}</button>
            </div>
        </form>
    );
}

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

export default function ProfilePage() {
    const { data: profile, error, reload, setData } = useApi(getProfile);
    const [copied, setCopied] = useState(false);

    const copyLink = async () => {
        if (!profile) return;
        await navigator.clipboard.writeText(`${window.location.origin}/pilots/${encodeURIComponent(profile.username)}`);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <PageShell>
            <PageHeader
                eyebrow="Profile"
                title={profile ? profile.username : 'Your profile'}
                description={profile ? `Logging since ${formatDate(profile.date_joined, 'long')}.` : undefined}
                action={
                    profile?.is_public && (
                        <div className="flex flex-wrap gap-2">
                            <Link href={`/pilots/${encodeURIComponent(profile.username)}`} className="btn btn-ghost">View public page</Link>
                            <button onClick={copyLink} className="btn btn-primary">
                                <ShareIcon className="h-4 w-4" />
                                {copied ? 'Link copied' : 'Copy link'}
                            </button>
                        </div>
                    )
                }
            />
            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !profile ? (
                <Spinner label="Finding your details" />
            ) : (
                <>
                    <ProfileForm profile={profile} onSaved={(saved) => setData(() => saved)} />
                    <Section title="Password">
                        <PasswordForm />
                    </Section>
                </>
            )}
        </PageShell>
    );
}
