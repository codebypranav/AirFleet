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

    const testApiConnection = async () => {
        try {
            const response = await fetch(`${info.fullApiUrl}/register/`, {
                method: 'HEAD'
            });
            alert(`API connection test: ${response.status} ${response.statusText}`);
        } catch (error) {
            alert(`API connection failed: ${error}`);
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
            
            <div className="flex space-x-4 mb-8">
                <button
                    onClick={testApiConnection}
                    className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700"
                >
                    Test API Connection
                </button>
                
                <Link href="/" className="px-4 py-2 bg-gray-600 rounded hover:bg-gray-700">
                    Back to Home
                </Link>
            </div>
        </div>
    );
} 