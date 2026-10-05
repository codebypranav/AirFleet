"use client";

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { PageShell, PageHeader, EmptyState, Spinner } from '@/components/PageShell';
import { PlaneIcon } from '@/components/Icons';
import { formatDuration } from '@/utils/format';
import { Flight } from '@/types/flight';
import Cookies from 'js-cookie';

interface NarrativeMap {
    [key: string]: string;
}

// Use environment variable with fallback
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
// Ensure the API URL doesn't have a trailing slash before adding /api
const BASE_URL = `${apiUrl.endsWith('/') ? apiUrl.slice(0, -1) : apiUrl}/api`;

export default function FlightNarrativePage() {
    const [flights, setFlights] = useState<Flight[]>([]);
    const [narratives, setNarratives] = useState<NarrativeMap>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const router = useRouter();

    const getAuthToken = () => {
        // First try to get token from Cookies (preferred method)
        const token = Cookies.get('accessToken');
        if (token) return token;
        
        // Fallback to looking in document.cookie directly
        const cookieMatch = document.cookie.match('accessToken=(.*?)(;|$)');
        return cookieMatch ? cookieMatch[1] : null;
    };

    const generateNarratives = useCallback(async (flightData: Flight[]) => {
        const token = getAuthToken();
        
        if (!token) {
            console.error('No authentication token found');
            setError('Authentication error. Please log in again.');
            router.push('/login');
            return;
        }

        for (const flight of flightData) {
            setNarratives(prev => ({
                ...prev,
                [flight.id]: 'Generating narrative...'
            }));
            
            try {
                console.log(`Generating narrative for flight ${flight.id}...`);
                console.log(`POST ${BASE_URL}/generate-narrative/`);
                
                const payload = {
                    flight_id: flight.id,
                    departure_time: flight.departure_time,
                    arrival_time: flight.arrival_time,
                    departure_airport: flight.departure_airport,
                    arrival_airport: flight.arrival_airport,
                    total_time: flight.total_time,
                    aircraft_condition: flight.aircraft_condition,
                    distance: flight.distance,
                    registration_number: flight.registration_number
                };
                
                console.log('Request payload:', payload);
                
                const response = await fetch(`${BASE_URL}/generate-narrative/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(payload)
                });

                if (response.status === 401) {
                    console.error('Authentication failed when generating narrative');
                    setError('Your session has expired. Please log in again.');
                    router.push('/login');
                    return;
                }

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`Server error: ${response.status} ${response.statusText}`);
                    console.error(`Response body: ${errorText}`);
                    throw new Error(`Failed to generate narrative: ${response.status} ${response.statusText}`);
                }

                const data = await response.json();
                console.log(`Got narrative response:`, data);
                
                setNarratives(prev => ({
                    ...prev,
                    [flight.id]: data.narrative
                }));
            } catch (error) {
                console.error(`Error generating narrative for flight ${flight.id}:`, error);
                setNarratives(prev => ({
                    ...prev,
                    [flight.id]: 'Failed to generate narrative. Please try again later.'
                }));
            }
        }
    }, [router]);

    useEffect(() => {
        const token = getAuthToken();
        if (!token) {
            console.error('No authentication token found');
            router.push('/login');
            return;
        }

        let ignore = false;
        fetch(`${BASE_URL}/flights/`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
            .then(async (response) => {
                if (ignore) return;

                if (response.status === 401) {
                    console.error('Authentication failed');
                    setError('Your session has expired. Please log in again.');
                    router.push('/login');
                    return;
                }

                if (!response.ok) {
                    throw new Error(`Failed to fetch flights: ${response.status} ${response.statusText}`);
                }

                const data = await response.json();
                if (ignore) return;
                setFlights(data);
                generateNarratives(data);
            })
            .catch((error) => {
                console.error('Error fetching flights:', error);
                if (!ignore) setError('Failed to fetch flights');
            })
            .finally(() => {
                if (!ignore) setLoading(false);
            });

        return () => {
            ignore = true;
        };
    }, [router, generateNarratives]);

    const header = (
        <PageHeader
            eyebrow="Stories"
            title="Flight narratives"
            description="Each entry in your logbook, retold as a short story."
        />
    );

    if (loading) {
        return (
            <PageShell>
                {header}
                <Spinner label="Gathering your flights" />
            </PageShell>
        );
    }

    return (
        <PageShell>
            {header}
            {error && <p className="alert-error mb-6" role="alert">{error}</p>}

            {!error && flights.length === 0 && (
                <EmptyState title="No stories yet">
                    <p>Once you log a flight, its story will be written here.</p>
                </EmptyState>
            )}

            <div className="space-y-6">
                {flights.map((flight, i) => {
                    const narrative = narratives[flight.id] || 'Generating narrative...';
                    const pending = narrative === 'Generating narrative...';
                    const departed = new Date(flight.departure_time);
                    return (
                        <article
                            key={flight.id}
                            className="card grid overflow-hidden md:grid-cols-[13rem_1fr] animate-rise"
                            style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
                        >
                            <aside className="flex flex-col gap-4 border-b border-line bg-graphite/40 p-5 md:border-b-0 md:border-r">
                                <p className="eyebrow">
                                    {departed.toLocaleDateString(undefined, { day: '2-digit', month: 'long', year: 'numeric' })}
                                </p>
                                <p className="flex items-center gap-2 font-mono text-2xl font-medium tracking-wider text-paper">
                                    {flight.departure_airport}
                                    <PlaneIcon className="h-4 w-4 rotate-90 text-moss" />
                                    {flight.arrival_airport}
                                </p>
                                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm md:grid-cols-1">
                                    <div>
                                        <dt className="eyebrow">Off / On</dt>
                                        <dd className="mt-0.5 font-mono text-bone">
                                            {departed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                            {' – '}
                                            {new Date(flight.arrival_time).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                                        </dd>
                                    </div>
                                    <div>
                                        <dt className="eyebrow">Duration</dt>
                                        <dd className="mt-0.5 text-bone">{formatDuration(flight.total_time)}</dd>
                                    </div>
                                    <div>
                                        <dt className="eyebrow">Distance</dt>
                                        <dd className="mt-0.5 text-bone">{flight.distance} nm</dd>
                                    </div>
                                </dl>
                            </aside>

                            <div className="p-6 sm:p-8">
                                <h2 className="eyebrow mb-4 text-clay">Flight story</h2>
                                {pending ? (
                                    <div className="space-y-3" role="status" aria-label="Generating narrative">
                                        <div className="h-3 w-11/12 animate-pulse rounded bg-graphite" />
                                        <div className="h-3 w-full animate-pulse rounded bg-graphite [animation-delay:150ms]" />
                                        <div className="h-3 w-4/5 animate-pulse rounded bg-graphite [animation-delay:300ms]" />
                                        <p className="pt-2 font-display text-sm italic text-ash">Writing it down…</p>
                                    </div>
                                ) : (
                                    <p className="font-display text-lg font-light leading-relaxed text-bone first-letter:float-left first-letter:mr-2 first-letter:font-display first-letter:text-5xl first-letter:font-medium first-letter:leading-[0.9] first-letter:text-fern">
                                        {narrative}
                                    </p>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>
        </PageShell>
    );
}
