"use client";

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
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

    const fetchFlights = useCallback(async () => {
        try {
            const token = getAuthToken();
            
            if (!token) {
                console.error('No authentication token found');
                setError('You must be logged in to view flights');
                router.push('/login');
                return;
            }

            const response = await fetch(`${BASE_URL}/flights/`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            
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
            setFlights(data);
            generateNarratives(data);
        } catch (error) {
            console.error('Error fetching flights:', error);
            setError('Failed to fetch flights');
        } finally {
            setLoading(false);
        }
    }, [router]);

    useEffect(() => {
        fetchFlights();
    }, [fetchFlights]);

    const generateNarratives = async (flightData: Flight[]) => {
        const token = getAuthToken();
        
        if (!token) {
            console.error('No authentication token found');
            setError('Authentication error. Please log in again.');
            router.push('/login');
            return;
        }

        for (const flight of flightData) {
            // Check if the flight already has a stored narrative
            if (flight.generated_narrative) {
                setNarratives(prev => ({
                    ...prev,
                    [flight.id]: flight.generated_narrative
                }));
                continue;
            }
            
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
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-black text-white">
                <Navbar />
                <div className="container mx-auto px-4 py-8">
                    <div className="flex justify-center items-center h-64">
                        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-black text-white">
            <Navbar />
            <div className="container mx-auto px-4 py-8">
                <h1 className="text-3xl font-bold mb-8">Flight Narratives</h1>
                {error && <p className="text-red-500 mb-4">{error}</p>}
                
                <div className="space-y-6">
                    {flights.map((flight) => (
                        <div key={flight.id} className="bg-gray-800 rounded-lg p-6">
                            <div className="flex justify-between items-start mb-4">
                                <h2 className="text-xl font-semibold">
                                    {flight.departure_airport} → {flight.arrival_airport}
                                </h2>
                                <span className="text-gray-400">
                                    {new Date(flight.departure_time).toLocaleDateString()}
                                </span>
                            </div>
                            
                            <div className="grid grid-cols-2 gap-4 mb-4 text-sm text-gray-300">
                                <div>
                                    <p>Departure: {new Date(flight.departure_time).toLocaleTimeString()}</p>
                                    <p>Arrival: {new Date(flight.arrival_time).toLocaleTimeString()}</p>
                                </div>
                                <div>
                                    <p>Duration: {flight.total_time}</p>
                                    <p>Distance: {flight.distance} nm</p>
                                </div>
                            </div>
                            
                            <div className="mt-4">
                                <h3 className="text-lg font-semibold mb-2">Flight Story</h3>
                                <p className="text-gray-300">
                                    {narratives[flight.id] || 'Generating narrative...'}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}