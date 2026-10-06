import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Signed-in pilots skip these and go straight to their logbook.
const GUEST_ONLY = new Set(['/', '/login', '/register'])
// Open to everyone, signed in or not.
const PUBLIC_PREFIXES = ['/forgot-password', '/reset-password', '/auth/complete', '/pilots/', '/share/', '/privacy', '/home_bg.jpg']

export function proxy(request: NextRequest) {
    const path = request.nextUrl.pathname
    // A refresh token is enough: the client swaps it for a fresh access token on its first request.
    const signedIn = Boolean(request.cookies.get('accessToken')?.value || request.cookies.get('refreshToken')?.value)

    if (GUEST_ONLY.has(path)) {
        return signedIn ? NextResponse.redirect(new URL('/flights', request.url)) : undefined
    }
    if (PUBLIC_PREFIXES.some((prefix) => path.startsWith(prefix))) {
        return undefined
    }
    if (!signedIn) {
        return NextResponse.redirect(new URL('/login', request.url))
    }
}

// Configure which paths the proxy should run on
export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico, icon.svg (favicon files)
         */
        '/((?!api|_next/static|_next/image|favicon.ico|icon.svg).*)',
    ],
}
