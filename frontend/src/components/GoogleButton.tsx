"use client";

import { useEffect, useState } from 'react';
import { getProviders, signIn } from 'next-auth/react';

/** "Continue with Google", shown only when the server has a Google provider configured. */
export default function GoogleButton() {
    const [enabled, setEnabled] = useState(false);

    useEffect(() => {
        getProviders()
            .then((providers) => setEnabled(Boolean(providers?.google)))
            .catch(() => setEnabled(false));
    }, []);

    if (!enabled) return null;

    return (
        <>
            <div className="flex items-center gap-3 text-xs text-ash">
                <span className="h-px flex-1 bg-line" />
                or
                <span className="h-px flex-1 bg-line" />
            </div>
            <button type="button" onClick={() => signIn('google', { callbackUrl: '/auth/complete' })} className="btn btn-ghost w-full py-3">
                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4">
                    <path fill="#EA4335" d="M12 10.2v3.9h5.4c-.24 1.4-1.66 4.1-5.4 4.1-3.25 0-5.9-2.69-5.9-6s2.65-6 5.9-6c1.85 0 3.09.79 3.8 1.47l2.59-2.5C16.73 3.6 14.6 2.6 12 2.6 6.81 2.6 2.6 6.81 2.6 12s4.21 9.4 9.4 9.4c5.43 0 9.03-3.81 9.03-9.19 0-.62-.07-1.09-.15-1.56H12Z" />
                </svg>
                Continue with Google
            </button>
        </>
    );
}
