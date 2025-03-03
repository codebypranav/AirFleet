"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Navbar from '@/components/Navbar';
import { Flight } from '@/types/flight';

interface NarrativeMap {
    [key: string]: string;
}

// Use environment variable with fallback
const BASE_URL = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api`;

export default function FlightNarrativePage() {
    const [flights, setFlights] = useState<Flight[]>([]);
    const [narratives, setNarratives] = useState<NarrativeMap>({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const router = useRouter();

    useEffect(() => {
        fetchFlights();
    }, []);

    const fetchFlights = async () => {
        try {
            const response = await fetch(`${BASE_URL}/flights/`, {
                headers: {
                    'Authorization': `Bearer ${document.cookie.match('accessToken=(.*?);')?.[1]}`
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch flights');
            }

            const data = await response.json();
            setFlights(data);
            generateNarratives(data);
        } catch (error) {
            console.error('Error fetching flights:', error);
            setError('Failed to fetch flights');
            if (error instanceof Error && error.message.includes('401')) {
                router.push('/login');
            }
        } finally {
            setLoading(false);
        }
    };

    const generateNarratives = async (flightData: Flight[]) => {
        for (const flight of flightData) {
            try {
                const response = await fetch(`${BASE_URL}/generate-narrative/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${document.cookie.match('accessToken=(.*?);')?.[1]}`
                    },
                    body: JSON.stringify({
                        flight_id: flight.id,
                        departure_time: flight.departure_time,
                        arrival_time: flight.arrival_time,
                        departure_airport: flight.departure_airport,
                        arrival_airport: flight.arrival_airport,
                        total_time: flight.total_time,
                        aircraft_condition: flight.aircraft_condition,
                        distance: flight.distance,
                        registration_number: flight.registration_number
                    })
                });

                if (!response.ok) {
                    throw new Error('Failed to generate narrative');
                }

                const data = await response.json();
                setNarratives(prev => ({
                    ...prev,
                    [flight.id]: data.narrative
                }));
            } catch (error) {
                console.error('Error generating narrative:', error);
                setNarratives(prev => ({
                    ...prev,
                    [flight.id]: 'Failed to generate narrative'
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