import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

// NextAuth only handles "Sign in with Google". Once Google returns an ID token, the
// Django API swaps it for AirFleet's own JWTs, which /auth/complete moves into the
// same cookies a password login uses.
const API_ORIGIN = (process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
    .replace(/\/+$/, "")
    .replace(/\/api$/, "");

export const googleEnabled = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

type AirfleetTokens = { access: string; refresh: string };

async function exchangeGoogleToken(idToken: string): Promise<AirfleetTokens | { error: string }> {
    try {
        const response = await fetch(`${API_ORIGIN}/api/auth/google/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: idToken }),
        });
        const data = await response.json();
        return response.ok ? { access: data.access, refresh: data.refresh } : { error: data.error || "Google sign-in failed" };
    } catch {
        return { error: "Couldn't reach the AirFleet API" };
    }
}

export const authOptions: NextAuthOptions = {
    secret: process.env.NEXTAUTH_SECRET,
    session: {
        strategy: "jwt",
        // Only needs to live long enough for /auth/complete to pick the tokens up.
        maxAge: 10 * 60,
    },
    providers: googleEnabled
        ? [
            GoogleProvider({
                clientId: process.env.GOOGLE_CLIENT_ID!,
                clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
            }),
        ]
        : [],
    callbacks: {
        async jwt({ token, account }) {
            if (account?.provider === "google" && account.id_token) {
                const result = await exchangeGoogleToken(account.id_token);
                if ("error" in result) {
                    token.airfleetError = result.error;
                } else {
                    token.airfleet = result;
                }
            }
            return token;
        },
        async session({ session, token }) {
            return { ...session, airfleet: token.airfleet ?? null, airfleetError: token.airfleetError ?? null };
        },
    },
    pages: {
        signIn: "/login",
        error: "/login",
    },
};
