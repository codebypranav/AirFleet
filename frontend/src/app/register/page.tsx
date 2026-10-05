"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import AuthLayout from '@/components/AuthLayout';

// Use environment variable with fallback - don't add /api as it might already be in the URL
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Check if the URL already ends with /api to avoid duplication
const BASE_URL = apiUrl.endsWith('/api') ? apiUrl : `${apiUrl}/api`;

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
        
        // Debug info
        console.log('API URL:', process.env.NEXT_PUBLIC_API_URL);
        console.log('BASE_URL:', BASE_URL);
        console.log('Full request URL:', `${BASE_URL}/register/`);

        try {
            const response = await fetch(`${BASE_URL}/register/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Registration failed: Server Error');
            }

            // Store tokens
            localStorage.setItem('accessToken', data.access);
            localStorage.setItem('refreshToken', data.refresh);

            router.push('/login');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Registration failed: This Username or Email is already in use');
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
