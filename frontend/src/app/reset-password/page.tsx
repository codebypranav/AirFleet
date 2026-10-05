"use client";

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import AuthLayout from '@/components/AuthLayout';
import { confirmPasswordReset } from '@/utils/api';

function ResetForm() {
    const params = useSearchParams();
    const uid = params.get('uid') ?? '';
    const token = params.get('token') ?? '';
    const [password, setPassword] = useState('');
    const [password2, setPassword2] = useState('');
    const [done, setDone] = useState(false);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);

    if (!uid || !token) {
        return (
            <div className="flex flex-col gap-5">
                <p className="alert-error" role="alert">This reset link is incomplete. Request a new one.</p>
                <Link href="/forgot-password" className="btn btn-primary w-full py-3">Request a new link</Link>
            </div>
        );
    }

    if (done) {
        return (
            <div className="flex flex-col gap-5">
                <p className="text-stone" role="status">Your password has been reset.</p>
                <Link href="/login" className="btn btn-primary w-full py-3">Log in</Link>
            </div>
        );
    }

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (password !== password2) {
            setError("The passwords don't match.");
            return;
        }
        setBusy(true);
        setError('');
        try {
            await confirmPasswordReset(uid, token, password);
            setDone(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not reset your password');
        } finally {
            setBusy(false);
        }
    };

    return (
        <form onSubmit={submit} className="flex flex-col gap-5">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div>
                <label htmlFor="password" className="field-label">New password</label>
                <input id="password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} className="field-input" />
            </div>
            <div>
                <label htmlFor="password2" className="field-label">Confirm new password</label>
                <input id="password2" type="password" autoComplete="new-password" value={password2} onChange={(e) => setPassword2(e.target.value)} required minLength={8} className="field-input" />
            </div>
            <button type="submit" className="btn btn-primary mt-2 w-full py-3" disabled={busy}>{busy ? 'Saving…' : 'Set new password'}</button>
        </form>
    );
}

export default function ResetPasswordPage() {
    return (
        <AuthLayout eyebrow="Account" title="Choose a new password">
            <Suspense fallback={null}>
                <ResetForm />
            </Suspense>
        </AuthLayout>
    );
}
