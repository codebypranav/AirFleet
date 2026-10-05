"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import AuthLayout from '@/components/AuthLayout';
import GoogleButton from '@/components/GoogleButton';
import { apiJson, saveTokens } from '@/utils/api';

export default function RegisterPage() {
    const router = useRouter();
    const [formData, setFormData] = useState({
        username: '',
        email: '',
        password: '',
        password2: ''
    });
    const [error, setError] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            saveTokens(await apiJson<{ access: string; refresh: string }>('/register/', { method: 'POST', json: formData, auth: false }));
            router.push('/flights');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Registration failed');
        }
    };

    return (
        <AuthLayout eyebrow="New logbook" title="Create an account">
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
                    <label htmlFor="email" className="field-label">Email</label>
                    <input
                        type="email"
                        id="email"
                        autoComplete="email"
                        value={formData.email}
                        onChange={(e) => setFormData({...formData, email: e.target.value})}
                        className="field-input"
                        required
                    />
                </div>

                <div>
                    <label htmlFor="password" className="field-label">Password</label>
                    <input
                        type="password"
                        id="password"
                        autoComplete="new-password"
                        value={formData.password}
                        onChange={(e) => setFormData({...formData, password: e.target.value})}
                        className="field-input"
                        required
                    />
                </div>

                <div>
                    <label htmlFor="password2" className="field-label">Confirm password</label>
                    <input
                        type="password"
                        id="password2"
                        autoComplete="new-password"
                        value={formData.password2}
                        onChange={(e) => setFormData({...formData, password2: e.target.value})}
                        className="field-input"
                        required
                    />
                </div>

                <button type="submit" className="btn btn-primary mt-2 w-full py-3">
                    Register
                </button>

                <GoogleButton />

                <p className="text-center text-xs text-ash">
                    See how we handle your logbook in the{' '}
                    <Link href="/privacy" className="text-fern underline-offset-4 hover:underline">privacy notice</Link>.
                </p>

                <p className="text-center text-sm text-ash">
                    Already have an account?{' '}
                    <Link href="/login" className="text-fern underline-offset-4 hover:underline">
                        Sign in
                    </Link>
                </p>
            </form>
        </AuthLayout>
    );
}
