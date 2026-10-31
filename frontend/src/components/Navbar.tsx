"use client";

import { useEffect, useRef, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import Avatar from '@/components/Avatar';
import { BrandMark, Wordmark } from '@/components/Brand';
import { ArrowIcon, BellIcon } from '@/components/Icons';
import { clearTokens, getProfile, getUnreadCount } from '@/utils/api';
import { useApi, usePoll } from '@/utils/useApi';

const GROUPS = [
    {
        label: 'Logbook',
        links: [
            { href: '/flights', label: 'Flights' },
            { href: '/aircraft', label: 'Fleet' },
            { href: '/stats', label: 'Stats' },
            { href: '/instruction', label: 'Instruction' },
        ],
    },
    {
        label: 'Community',
        links: [
            { href: '/following', label: 'Following' },
            { href: '/groups', label: 'Groups' },
            { href: '/rankings', label: 'Rankings' },
        ],
    },
];

const ITEM = 'block w-full rounded-lg px-3 py-2 text-left text-sm transition-colors';

function Menu({ trigger, label, active = false, right = false, buttonClass, children }: {
    trigger: React.ReactNode;
    label?: string;
    active?: boolean;
    right?: boolean;
    buttonClass: string;
    children: React.ReactNode;
}) {
    const [open, setOpen] = useState(false);
    const root = useRef<HTMLDivElement>(null);
    const button = useRef<HTMLButtonElement>(null);

    useEffect(() => {
        if (!open) return;
        const onPointer = (e: PointerEvent) => {
            if (!root.current?.contains(e.target as Node)) setOpen(false);
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key !== 'Escape') return;
            setOpen(false);
            button.current?.focus();
        };
        document.addEventListener('pointerdown', onPointer);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('pointerdown', onPointer);
            document.removeEventListener('keydown', onKey);
        };
    }, [open]);

    return (
        <div ref={root} className="relative" onBlur={(e) => !root.current?.contains(e.relatedTarget) && setOpen(false)}>
            <button
                ref={button}
                type="button"
                aria-label={label}
                aria-expanded={open}
                aria-current={active ? 'page' : undefined}
                onClick={() => setOpen((o) => !o)}
                className={buttonClass}
            >
                {trigger}
            </button>
            {open && (
                <div
                    onClick={() => setOpen(false)}
                    className={`absolute top-full z-50 mt-2 w-48 rounded-xl border border-line bg-ink p-1.5 shadow-lg ${right ? 'right-0' : 'left-0'}`}
                >
                    {children}
                </div>
            )}
        </div>
    );
}

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

function Account({ active }: { active: boolean }) {
    const router = useRouter();
    const { data: profile } = useApi(getProfile, 'me');

    const handleLogout = () => {
        clearTokens();
        router.push('/login');
    };

    return (
        <Menu
            label="Account"
            right
            active={active}
            buttonClass="rounded-full"
            trigger={profile ? <Avatar username={profile.username} avatar={profile.avatar} size={32} /> : <span className="block h-8 w-8 rounded-full border border-line bg-graphite" />}
        >
            {profile && <p className="truncate px-3 pb-2 pt-1 text-xs text-stone">{profile.username}</p>}
            <Link href="/profile" className={`${ITEM} text-ash hover:bg-graphite hover:text-bone`}>Edit profile</Link>
            <Link href="/settings" className={`${ITEM} text-ash hover:bg-graphite hover:text-bone`}>Settings</Link>
            <button type="button" onClick={handleLogout} className={`${ITEM} text-ash hover:bg-graphite hover:text-bone`}>Log out</button>
        </Menu>
    );
}

export default function Navbar({ variant = 'app' }: { variant?: 'app' | 'public' }) {
    const pathname = usePathname();

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
            <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-2 px-4 py-3 sm:gap-6 sm:px-6">
                <Link href="/flights" aria-label="AirFleet logbook" className="shrink-0">
                    <BrandMark className="h-9 w-9 text-fern sm:hidden" />
                    <span className="hidden sm:block">
                        <Wordmark />
                    </span>
                </Link>
                <div className="flex items-center gap-1">
                    {GROUPS.map(({ label, links }) => {
                        const active = links.some(({ href }) => isActive(href));
                        return (
                            <Menu
                                key={label}
                                active={active}
                                buttonClass={`relative flex items-center gap-1 rounded-full px-2.5 py-1.5 text-sm transition-colors sm:px-3.5 ${
                                    active ? 'bg-graphite text-paper' : 'text-ash hover:text-bone'
                                }`}
                                trigger={
                                    <>
                                        {active && <span className="absolute left-1 top-1/2 sm:left-1.5 h-1 w-1 -translate-y-1/2 rounded-full bg-moss" />}
                                        {label}
                                        <ArrowIcon className="h-3.5 w-3.5 rotate-90" />
                                    </>
                                }
                            >
                                {links.map(({ href, label }) => (
                                    <Link
                                        key={href}
                                        href={href}
                                        aria-current={isActive(href) ? 'page' : undefined}
                                        className={`${ITEM} ${isActive(href) ? 'bg-graphite text-paper' : 'text-ash hover:bg-graphite hover:text-bone'}`}
                                    >
                                        {label}
                                    </Link>
                                ))}
                            </Menu>
                        );
                    })}
                </div>
                <div className="flex items-center gap-1 sm:gap-2">
                    <Bell active={isActive('/notifications')} />
                    <Account active={isActive('/profile') || isActive('/settings')} />
                </div>
            </div>
        </nav>
    );
}
