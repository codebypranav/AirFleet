"use client";

import { useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { signOut, useSession } from 'next-auth/react';
import AuthLayout from '@/components/AuthLayout';
import { Spinner } from '@/components/PageShell';
import { saveTokens } from '@/utils/api';
import SessionProviderWrapper from '../../SessionProviderWrapper';

/** Landing page after Google sign-in: move AirFleet's tokens from the NextAuth session into cookies. */
function CompleteSignIn() {
    const router = useRouter();
    const { data: session, status } = useSession();
    const tokens = session?.airfleet;

    useEffect(() => {
        if (!tokens) return;
        saveTokens(tokens);
        // The NextAuth session was only a carrier; drop it now the cookies are set.
        signOut({ redirect: false }).finally(() => router.replace('/flights'));
    }, [tokens, router]);

    const failed = status === 'unauthenticated' || (status === 'authenticated' && !tokens);

    return (
        <AuthLayout eyebrow="Google sign-in" title={failed ? 'Sign-in failed' : 'Signing you in'}>
            {failed ? (
                <div className="flex flex-col gap-5">
                    <p className="alert-error" role="alert">{session?.airfleetError || 'Google sign-in did not complete. Please try again.'}</p>
                    <Link href="/login" className="btn btn-primary w-full py-3">Back to log in</Link>
                </div>
            ) : (
                <Spinner label="Opening your logbook" />
            )}
        </AuthLayout>
    );
}

// Only this page reads the NextAuth session, so only it needs the provider.
export default function AuthCompletePage() {
    return (
        <SessionProviderWrapper>
            <CompleteSignIn />
        </SessionProviderWrapper>
    );
}
