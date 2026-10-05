"use client";

import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import Cookies from 'js-cookie';
import { Wordmark } from '@/components/Brand';

const LINKS = [
    { href: '/flights', label: 'Logbook' },
    { href: '/flights/narrative', label: 'Stories' },
    { href: '/rankings', label: 'Rankings' },
];

export default function Navbar() {
    const router = useRouter();
    const pathname = usePathname();

    const handleLogout = () => {
        Cookies.remove('accessToken');
        Cookies.remove('refreshToken');

        router.push('/login');
    };

    // /flights/add belongs to the logbook; /flights/narrative has its own tab.
    const isActive = (href: string) =>
        href === '/flights' ? pathname === '/flights' || pathname === '/flights/add' : pathname.startsWith(href);

    return (
        <nav className="sticky top-0 z-40 border-b border-line/80 bg-ink/80 backdrop-blur-md">
            <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
                <Link href="/flights" aria-label="AirFleet logbook">
                    <Wordmark />
                </Link>
                <div className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto sm:order-none sm:mx-0 sm:w-auto">
                    {LINKS.map(({ href, label }) => (
                        <Link
                            key={href}
                            href={href}
                            aria-current={isActive(href) ? 'page' : undefined}
                            className={`relative rounded-full px-3.5 py-1.5 text-sm transition-colors ${
                                isActive(href)
                                    ? 'bg-graphite text-paper'
                                    : 'text-ash hover:text-bone'
                            }`}
                        >
                            {isActive(href) && (
                                <span className="absolute left-1.5 top-1/2 h-1 w-1 -translate-y-1/2 rounded-full bg-moss" />
                            )}
                            {label}
                        </Link>
                    ))}
                </div>
                <button onClick={handleLogout} className="btn btn-ghost px-4 py-1.5 text-ash hover:text-bone">
                    Log out
                </button>
            </div>
        </nav>
    );
}
