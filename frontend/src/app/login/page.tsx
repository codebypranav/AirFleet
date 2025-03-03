"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from 'next/link';
import Cookies from 'js-cookie';

// Use environment variable with fallback
const BASE_URL = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`;

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
            console.log('Tokens stored in cookies, attempting navigation');

            try {
                await router.push('/flights');
                console.log('Router.push completed');
            } catch (navError) {
                console.error('Navigation error:', navError);
                window.location.href = '/flights';
            }
        } catch (err) {
            console.error('Login error:', err);
            setError(err instanceof Error ? err.message : 'Login failed');
        }
    }

    return (
        <main className="relative min-h-screen flex flex-col px-4 bg-black">
            <div 
                className="absolute inset-0 z-0"
                style={{
                    backgroundImage: 'url("/home_bg.jpg")',
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                }}
            >
                <div className="absolute inset-0 bg-black/50"></div>
            </div>

            <div className="relative z-10 flex items-center justify-center min-h-screen">
                <form
                    onSubmit={handleSubmit}
                    className="flex flex-col gap-4 bg-black/80 p-8 rounded-lg shadow-xl backdrop-blur-sm w-full max-w-md"
                >
                    <h1 className="text-3xl font-bold text-white mb-2">Login</h1>
                    {error && <p className="text-red-400">{error}</p>}

                    <div>
                        <label htmlFor="username" className="block text-sm font-medium text-gray-200">Username</label>
                        <input
                            type="text"
                            id="username"
                            value={formData.username}
                            onChange={(e) => setFormData({...formData, username: e.target.value})}
                            className="mt-1 block w-full rounded-md bg-gray-800 border-gray-700 text-white"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="password" className="block text-sm font-medium text-gray-200">Password</label>
                        <input
                            type="password"
                            id="password"
                            value={formData.password}
                            onChange={(e) => setFormData({...formData, password: e.target.value})}
                            className="mt-1 block w-full rounded-md bg-gray-800 border-gray-700 text-white"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="w-full py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-black hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-black"
                    >
                        Sign In
                    </button>

                    <p className="text-center text-gray-300">
                        Don&apos;t have an account?{' '}
                        <Link href="/register" className="text-white hover:underline">
                            Register
                        </Link>
                    </p>
                </form>
            </div>
        </main>
    );
}
