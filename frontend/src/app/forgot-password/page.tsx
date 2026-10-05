"use client";

import { useState } from 'react';
import Link from 'next/link';
import AuthLayout from '@/components/AuthLayout';
import { requestPasswordReset } from '@/utils/api';

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [sent, setSent] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            setSent((await requestPasswordReset(email)).detail);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not send the email');
        } finally {
            setBusy(false);
        }
    };

    return (
        <AuthLayout eyebrow="Account" title="Reset your password">
            {sent ? (
                <div className="flex flex-col gap-5">
                    <p className="text-stone" role="status">{sent}</p>
                    <p className="text-sm text-ash">The link works once and expires after a few days. Check your spam folder if it doesn&apos;t arrive.</p>
                    <Link href="/login" className="btn btn-primary w-full py-3">Back to log in</Link>
                </div>
            ) : (
                <form onSubmit={submit} className="flex flex-col gap-5">
                    {error && <p className="alert-error" role="alert">{error}</p>}
                    <p className="text-sm text-stone">Enter the email you signed up with and we&apos;ll send you a link to choose a new password.</p>
                    <div>
                        <label htmlFor="email" className="field-label">Email</label>
                        <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="field-input" />
                    </div>
                    <button type="submit" className="btn btn-primary mt-2 w-full py-3" disabled={busy}>{busy ? 'Sending…' : 'Send reset link'}</button>
                    <p className="text-center text-sm text-ash">
                        Remembered it? <Link href="/login" className="text-fern underline-offset-4 hover:underline">Log in</Link>
                    </p>
                </form>
            )}
        </AuthLayout>
    );
}
