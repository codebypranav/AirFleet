"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from 'next/link';
import AuthLayout from '@/components/AuthLayout';
import GoogleButton from '@/components/GoogleButton';
import { apiJson, saveTokens } from '@/utils/api';

export default function LoginPage() {
    const router = useRouter();
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
            router.push('/flights');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Login failed');
        }
    }

    return (
        <AuthLayout eyebrow="Welcome back" title="Log in">
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
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
        </AuthLayout>
    );
}
