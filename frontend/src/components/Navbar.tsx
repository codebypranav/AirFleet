"use client";

import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Wordmark } from '@/components/Brand';
import { BellIcon } from '@/components/Icons';
import { clearTokens, getUnreadCount } from '@/utils/api';
import { useApi, usePoll } from '@/utils/useApi';

const LINKS = [
    { href: '/flights', label: 'Logbook' },
    { href: '/following', label: 'Following' },
    { href: '/aircraft', label: 'Fleet' },
    { href: '/stats', label: 'Stats' },
    { href: '/instruction', label: 'Instruction' },
    { href: '/rankings', label: 'Rankings' },
    { href: '/profile', label: 'Profile' },
];

function Bell({ active }: { active: boolean }) {
    const { data, reload } = useApi(getUnreadCount, 'unread');
    usePoll(reload);
    const count = active ? 0 : data?.count ?? 0;
    return (
        <Link
            href="/notifications"
            aria-label={count ? `Notifications, ${count} unread` : 'Notifications'}
            aria-current={active ? 'page' : undefined}
            className={`relative rounded-full p-2 transition-colors ${active ? 'bg-graphite text-paper' : 'text-ash hover:text-bone'}`}
        >
            <BellIcon className="h-5 w-5" />
            {count > 0 && (
                <span className="absolute -right-0.5 -top-0.5 min-w-[1.1rem] rounded-full bg-clay px-1 text-center text-[10px] font-medium leading-[1.1rem] text-ink">
                    {count > 99 ? '99+' : count}
                </span>
            )}
        </Link>
    );
}

export default function Navbar({ variant = 'app' }: { variant?: 'app' | 'public' }) {
    const router = useRouter();
    const pathname = usePathname();

    const handleLogout = () => {
        clearTokens();
        router.push('/login');
    };

    const isActive = (href: string) => pathname.startsWith(href);

    if (variant === 'public') {
        return (
            <nav className="sticky top-0 z-40 border-b border-line/80 bg-ink/80 backdrop-blur-md">
                <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-6 px-4 py-3 sm:px-6">
                    <Link href="/" aria-label="AirFleet home">
                        <Wordmark />
                    </Link>
                    <Link href="/flights" className="btn btn-ghost px-4 py-1.5 text-ash hover:text-bone">
                        Open your logbook
                    </Link>
                </div>
            </nav>
        );
    }

    return (
        <nav className="sticky top-0 z-40 border-b border-line/80 bg-ink/80 backdrop-blur-md">
            <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
                <Link href="/flights" aria-label="AirFleet logbook">
                    <Wordmark />
                </Link>
                <div className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto md:order-none md:mx-0 md:w-auto">
                    {LINKS.map(({ href, label }) => (
                        <Link
                            key={href}
                            href={href}
                            aria-current={isActive(href) ? 'page' : undefined}
                            className={`relative shrink-0 rounded-full px-3.5 py-1.5 text-sm transition-colors ${
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
                <div className="flex items-center gap-2">
                    <Bell active={isActive('/notifications')} />
                    <button onClick={handleLogout} className="btn btn-ghost px-4 py-1.5 text-ash hover:text-bone">
                        Log out
                    </button>
                </div>
            </div>
        </nav>
    );
}
