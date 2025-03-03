"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';

export default function DebugPage() {
    const [info, setInfo] = useState({
        apiUrl: "",
        fullApiUrl: "",
        vercelUrl: "",
        nextPublicApiUrl: ""
    });
    
    useEffect(() => {
        // Collect environment information
        setInfo({
            apiUrl: process.env.NEXT_PUBLIC_API_URL || 'Not set',
            fullApiUrl: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`,
            vercelUrl: process.env.VERCEL_URL || 'Not set',
            nextPublicApiUrl: process.env.NEXT_PUBLIC_API_URL || 'Not set'
        });
    }, []);

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
        <div className="min-h-screen bg-black text-white p-8">
            <h1 className="text-3xl font-bold mb-8">Debug Information</h1>
            
            <div className="bg-gray-800 p-4 rounded-lg mb-8">
                <h2 className="text-xl font-bold mb-4">Environment Variables</h2>
                <pre className="bg-gray-900 p-4 rounded overflow-auto max-w-full">
                    {JSON.stringify(info, null, 2)}
                </pre>
            </div>
            
            <div className="bg-gray-800 p-4 rounded-lg mb-8">
                <h2 className="text-xl font-bold mb-4">Test Different URL Patterns</h2>
                <div className="space-y-4">
                    {testUrls.map((test, index) => (
                        <div key={index} className="flex flex-col space-y-2">
                            <div className="flex justify-between">
                                <span>{test.name}</span>
                                <span className="text-gray-400">{test.url}</span>
                            </div>
                            <button
                                onClick={() => testApiConnection(test.url)}
                                className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 text-sm"
                            >
                                Test This URL
                            </button>
                        </div>
                    ))}
                </div>
            </div>
            
            <Link href="/" className="px-4 py-2 bg-gray-600 rounded hover:bg-gray-700">
                Back to Home
            </Link>
        </div>
    );
} 