"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from 'next/link';
import Cookies from 'js-cookie';
import AuthLayout from '@/components/AuthLayout';

// Use environment variable with fallback - don't add /api as it might already be in the URL
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Check if the URL already ends with /api to avoid duplication
const BASE_URL = apiUrl.endsWith('/api') ? apiUrl : `${apiUrl}/api`;

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
        console.log('Login attempt started');

        try {
            const response = await fetch(`${BASE_URL}/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            const data = await response.json();
            console.log('Login response:', data);

            if (!response.ok) {
                throw new Error(data.error || 'Login failed');
            }

            // Store tokens in cookies instead of localStorage
            Cookies.set('accessToken', data.access, { secure: true, sameSite: 'strict' });
            Cookies.set('refreshToken', data.refresh, { secure: true, sameSite: 'strict' });
            router.push('/flights');
        } catch (err) {
            console.error('Login error:', err);
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
                    <label htmlFor="password" className="field-label">Password</label>
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
