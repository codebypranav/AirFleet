"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from 'next/link';
import AuthLayout from '@/components/AuthLayout';
import GoogleButton from '@/components/GoogleButton';
import Cookies from 'js-cookie';
import { apiIsUp, apiJson, safeNext, saveTokens } from '@/utils/api';

/**
 * Shown when a page sent the pilot here because the server couldn't be reached (Render waking it up).
 * Polls the health check; a pilot who is still signed in goes straight back to `next` once it answers.
 */
function WakingNotice({ next }: { next: string }) {
    const router = useRouter();
    const [ready, setReady] = useState(false);
    const [signedIn] = useState(() => Boolean(Cookies.get('accessToken') || Cookies.get('refreshToken')));

    useEffect(() => {
        let stopped = false;
        let timer: ReturnType<typeof setTimeout>;
        const check = async () => {
            if (await apiIsUp()) {
                if (stopped) return;
                if (signedIn) router.replace(next);
                else setReady(true);
            } else if (!stopped) {
                timer = setTimeout(check, 5000);
            }
        };
        check();
        return () => {
            stopped = true;
            clearTimeout(timer);
        };
    }, [next, router, signedIn]);

    return (
        <p className="alert-info" role="status">
            {ready
                ? 'The server is awake. Log in to pick up where you left off.'
                : signedIn
                    ? 'The AirFleet server is waking up, which can take up to a minute. You’ll go straight back once it’s ready.'
                    : 'The AirFleet server is waking up, which can take up to a minute. Log in once it’s ready.'}
        </p>
    );
}

function LoginForm() {
    const router = useRouter();
    const params = useSearchParams();
    const next = safeNext(params.get('next'));
    const [error, setError] = useState("");
    const [formData, setFormData] = useState({
        username: '',
        password: '',
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        try {
            saveTokens(await apiJson<{ access: string; refresh: string }>('/login/', { method: 'POST', json: formData, auth: false }));
            router.push(next);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed');
        }
    }

    return (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {params.get('reason') === 'waking' && <WakingNotice next={next} />}
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div>
                <label htmlFor="username" className="field-label">Username</label>
                <input
                    type="text"
                    id="username"
                    autoComplete="username"
                    value={formData.username}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
                    className="field-input"
                    required
                />
            </div>

            <div>
                <div className="flex items-baseline justify-between">
                    <label htmlFor="password" className="field-label">Password</label>
                    <Link href="/forgot-password" className="text-xs text-fern underline-offset-4 hover:underline">Forgot it?</Link>
                </div>
                <input
                    type="password"
                    id="password"
                    autoComplete="current-password"
                    value={formData.password}
                    onChange={(e) => setFormData({...formData, password: e.target.value})}
                    className="field-input"
                    required
                />
            </div>

            <button type="submit" className="btn btn-primary mt-2 w-full py-3">
                Sign in
            </button>

            <GoogleButton />

            <p className="text-center text-sm text-ash">
                Don&apos;t have an account?{' '}
                <Link href="/register" className="text-fern underline-offset-4 hover:underline">
                    Register
                </Link>
            </p>
        </form>
    );
}

export default function LoginPage() {
    return (
        <AuthLayout eyebrow="Welcome back" title="Log in">
            <Suspense>
                <LoginForm />
            </Suspense>
        </AuthLayout>
    );
}
