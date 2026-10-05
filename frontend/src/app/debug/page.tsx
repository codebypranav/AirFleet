"use client";

import Link from 'next/link';
import { notFound } from 'next/navigation';

// NEXT_PUBLIC_* values are inlined at build time, so they match on server and client.
const info = {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || 'Not set',
    fullApiUrl: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`,
    vercelUrl: process.env.NEXT_PUBLIC_VERCEL_URL || 'Not set',
    nextPublicApiUrl: process.env.NEXT_PUBLIC_API_URL || 'Not set'
};

export default function DebugPage() {
    // Connection diagnostics for deploys; hidden unless explicitly switched on.
    if (process.env.NEXT_PUBLIC_ENABLE_DEBUG !== 'true') notFound();

    const testUrls = [
        { name: "Standard URL", url: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/register/` },
        { name: "URL without /api", url: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/register/` },
        { name: "URL with users app prefix", url: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/users/register/` }
    ];

    const testApiConnection = async (url: string) => {
        try {
            console.log(`Testing URL: ${url}`);
            const response = await fetch(url, {
                method: 'HEAD'
            });
            alert(`API test (${url}): ${response.status} ${response.statusText}`);
        } catch (error) {
            alert(`API test failed (${url}): ${error}`);
        }
    };

    return (
        <div className="mx-auto min-h-screen max-w-3xl bg-ink p-6 text-bone sm:p-10">
            <p className="eyebrow mb-3">Diagnostics</p>
            <h1 className="mb-8 font-display text-4xl font-medium text-paper">Debug information</h1>
            
            <div className="card mb-6 p-5">
                <h2 className="eyebrow mb-4 text-clay">Environment Variables</h2>
                <pre className="max-w-full overflow-auto rounded-lg border border-line bg-graphite p-4 font-mono text-sm text-stone">
                    {JSON.stringify(info, null, 2)}
                </pre>
            </div>
            
            <div className="card mb-6 p-5">
                <h2 className="eyebrow mb-4 text-clay">Test Different URL Patterns</h2>
                <div className="space-y-4">
                    {testUrls.map((test, index) => (
                        <div key={index} className="flex flex-col space-y-2">
                            <div className="flex flex-wrap justify-between gap-2">
                                <span>{test.name}</span>
                                <span className="break-all font-mono text-xs text-ash">{test.url}</span>
                            </div>
                            <button
                                onClick={() => testApiConnection(test.url)}
                                className="btn btn-ghost self-start"
                            >
                                Test This URL
                            </button>
                        </div>
                    ))}
                </div>
            </div>
            
            <Link href="/" className="btn btn-primary">
                Back to Home
            </Link>
        </div>
    );
} 