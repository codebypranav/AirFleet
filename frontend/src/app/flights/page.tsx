"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { getFlights } from '@/utils/api';
import { useRouter } from 'next/navigation';
import { PageShell, PageHeader, EmptyState, Spinner } from '@/components/PageShell';
import { CameraIcon, PlaneIcon, PlusIcon } from '@/components/Icons';
import { conditionFor, durationToSeconds, formatDuration, formatHours, photoUrl } from '@/utils/format';

interface Flight {
    id: number;
    departure_time: string;
    arrival_time: string;
    total_time: string;
    departure_airport: string;
    arrival_airport: string;
    registration_number: string;
    aircraft_condition: string;
    distance: number;
    photo?: string;
}

export default function FlightsPage() {
    const [flights, setFlights] = useState<Flight[]>([]);
    const [loading, setLoading] = useState(true);
    const router = useRouter();

    useEffect(() => {
        const fetchFlights = async () => {
            try {
                const data = await getFlights();
                setFlights(data);
            } catch (error) {
                console.error('Error fetching flights:', error);
                // Redirect to login if unauthorized
                if (error instanceof Error && error.message.includes('401')) {
                    router.push('/login');
                }
            } finally {
                setLoading(false);
            }
        };

        fetchFlights();
    }, [router]);

    const totalSeconds = flights.reduce((sum, f) => sum + durationToSeconds(f.total_time), 0);
    const totalDistance = flights.reduce((sum, f) => sum + (Number(f.distance) || 0), 0);
    const airframes = new Set(flights.map((f) => f.registration_number)).size;
    const stats = [
        { label: 'Legs', value: flights.length.toLocaleString() },
        { label: 'Total time', value: formatHours(totalSeconds) },
        { label: 'Distance', value: `${totalDistance.toLocaleString()} nm` },
        { label: 'Airframes', value: airframes.toLocaleString() },
    ];

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook"
                title="My flights"
                description="Every leg you've flown, newest entries first."
                action={
                    <Link href="/flights/add" className="btn btn-primary">
                        <PlusIcon className="h-4 w-4" />
                        Add flight
                    </Link>
                }
            />

            {loading ? (
                <Spinner label="Opening the logbook" />
            ) : flights.length === 0 ? (
                <EmptyState title="A blank first page">
                    <p>Log your first flight and it will show up here, with time, distance and photos.</p>
                    <Link href="/flights/add" className="btn btn-primary mt-6">
                        <PlusIcon className="h-4 w-4" />
                        Log a flight
                    </Link>
                </EmptyState>
            ) : (
                <>
                    <dl className="mb-10 grid grid-cols-2 overflow-hidden rounded-xl border border-line bg-line gap-px sm:grid-cols-4 animate-rise">
                        {stats.map((stat) => (
                            <div key={stat.label} className="bg-char px-5 py-4">
                                <dt className="eyebrow">{stat.label}</dt>
                                <dd className="mt-1 font-display text-2xl text-paper sm:text-3xl">{stat.value}</dd>
                            </div>
                        ))}
                    </dl>

                    <ol className="space-y-4">
                        {flights.map((flight, i) => {
                            const condition = conditionFor(flight.aircraft_condition);
                            const departed = new Date(flight.departure_time);
                            return (
                                <li
                                    key={flight.id}
                                    className="card group flex flex-col overflow-hidden transition-colors hover:border-ash/50 sm:flex-row animate-rise"
                                    style={{ animationDelay: `${Math.min(i, 8) * 50}ms` }}
                                >
                                    <div className="flex flex-1 flex-col gap-5 p-5 sm:p-6">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <p className="eyebrow">
                                                {departed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })}
                                                {' · '}
                                                {departed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                            </p>
                                            <span className={`rounded-full border px-2.5 py-0.5 text-xs ${condition.className}`}>
                                                {condition.label}
                                            </span>
                                        </div>

                                        <div className="flex items-center gap-4">
                                            <span className="font-mono text-3xl font-medium tracking-wider text-paper sm:text-4xl">
                                                {flight.departure_airport}
                                            </span>
                                            <span className="relative flex flex-1 items-center">
                                                <span className="w-full border-t border-dashed border-ash/50" />
                                                <PlaneIcon className="absolute left-1/2 h-5 w-5 -translate-x-1/2 rotate-90 bg-char px-0.5 text-moss transition-transform duration-500 group-hover:translate-x-4" />
                                            </span>
                                            <span className="font-mono text-3xl font-medium tracking-wider text-paper sm:text-4xl">
                                                {flight.arrival_airport}
                                            </span>
                                        </div>

                                        <dl className="grid grid-cols-3 gap-4 border-t border-dashed border-line pt-4 text-sm">
                                            <div>
                                                <dt className="eyebrow">Block time</dt>
                                                <dd className="mt-1 text-bone">{formatDuration(flight.total_time)}</dd>
                                            </div>
                                            <div>
                                                <dt className="eyebrow">Distance</dt>
                                                <dd className="mt-1 text-bone">{flight.distance} nm</dd>
                                            </div>
                                            <div>
                                                <dt className="eyebrow">Aircraft</dt>
                                                <dd className="mt-1 font-mono text-bone">{flight.registration_number}</dd>
                                            </div>
                                        </dl>
                                    </div>

                                    {flight.photo ? (
                                        <div className="relative h-48 border-t border-line sm:h-auto sm:w-56 sm:border-l sm:border-t-0">
                                            <Image
                                                src={photoUrl(flight.photo)}
                                                alt={`Photo from ${flight.departure_airport} to ${flight.arrival_airport}`}
                                                fill
                                                sizes="(min-width: 640px) 224px, 100vw"
                                                // Photos are short-lived signed links from Neon Object Storage,
                                                // so the browser loads them directly instead of via the optimizer.
                                                unoptimized
                                                className="object-cover grayscale-[35%] sepia-[15%] transition duration-500 group-hover:grayscale-0 group-hover:sepia-0"
                                            />
                                        </div>
                                    ) : (
                                        <div className="hidden items-center justify-center border-l border-line bg-graphite/40 text-line sm:flex sm:w-56">
                                            <CameraIcon className="h-8 w-8" />
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ol>
                </>
            )}
        </PageShell>
    );
}
