"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { PageShell, PageHeader } from '@/components/PageShell';
import { CameraIcon } from '@/components/Icons';
import { CONDITIONS } from '@/utils/format';
import { addFlight } from '@/utils/api';

export default function AddFlight() {
    const router = useRouter();
    const [formData, setFormData] = useState({
        departure_time: '',
        arrival_time: '',
        departure_airport: '',
        arrival_airport: '',
        registration_number: '',
        aircraft_condition: 'AIRWORTHY',
        distance: 0,
        photo: null as File | null,
    });
    const [error, setError] = useState('');

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: value
        }));
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFormData(prev => ({
                ...prev,
                photo: e.target.files![0]
            }));
        }
    };

    const calculateTotalTime = () => {
        if (formData.departure_time && formData.arrival_time) {
            const departure = new Date(formData.departure_time);
            const arrival = new Date(formData.arrival_time);
            const diffInSeconds = (arrival.getTime() - departure.getTime()) / 1000;
            const hours = Math.floor(diffInSeconds / 3600);
            const minutes = Math.floor((diffInSeconds % 3600) / 60);
            const seconds = Math.floor(diffInSeconds % 60);
            return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        return '0:00:00';
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            const totalTime = calculateTotalTime();
            const flightData = new FormData();
            
            Object.entries(formData).forEach(([key, value]) => {
                if (value !== null) {
                    if (key === 'photo' && value instanceof File) {
                        flightData.append(key, value);
                    } else if (typeof value === 'number') {
                        flightData.append(key, value.toString());
                    } else if (typeof value === 'string') {
                        flightData.append(key, value);
                    }
                }
            });
            
            flightData.append('total_time', totalTime);

            await addFlight(flightData);
            router.push('/flights');
            router.refresh();
        } catch (error) {
            setError('Failed to add flight. Please try again.');
            console.error('Error adding flight:', error);
            if (error instanceof Error && error.message.includes('401')) {
                router.push('/login');
            }
        }
    };

    const blockTime = calculateTotalTime();
    const blockTimeValid = !blockTime.startsWith('-') && blockTime !== '0:00:00';

    const field = (name: 'departure_airport' | 'arrival_airport' | 'registration_number', label: string, placeholder: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
        <div>
            <label htmlFor={name} className="field-label">{label}</label>
            <input
                type="text"
                id={name}
                name={name}
                value={formData[name]}
                onChange={handleChange}
                required
                placeholder={placeholder}
                className="field-input font-mono uppercase tracking-wider placeholder:normal-case placeholder:tracking-normal"
                {...extra}
            />
        </div>
    );

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook · New entry"
                title="Add a flight"
                description="Fill in the leg as you'd write it in the paper log. Block time is worked out for you."
            />

            <form onSubmit={handleSubmit} className="space-y-6 animate-rise">
                {error && (
                    <div className="alert-error" role="alert">
                        {error}
                    </div>
                )}

                <fieldset className="card p-5 sm:p-6">
                    <legend className="sr-only">Times</legend>
                    <p className="eyebrow mb-5 text-clay">01 · Times</p>
                    <div className="grid grid-cols-1 gap-5 md:grid-cols-[1fr_1fr_auto] md:items-end">
                        <div>
                            <label htmlFor="departure_time" className="field-label">Departure</label>
                            <input
                                type="datetime-local"
                                id="departure_time"
                                name="departure_time"
                                value={formData.departure_time}
                                onChange={handleChange}
                                required
                                className="field-input"
                            />
                        </div>
                        <div>
                            <label htmlFor="arrival_time" className="field-label">Arrival</label>
                            <input
                                type="datetime-local"
                                id="arrival_time"
                                name="arrival_time"
                                value={formData.arrival_time}
                                onChange={handleChange}
                                required
                                className="field-input"
                            />
                        </div>
                        <div className="rounded-lg border border-dashed border-line px-4 py-2.5 md:min-w-36">
                            <p className="eyebrow">Block time</p>
                            <p className={`font-mono text-lg ${blockTimeValid ? 'text-fern' : 'text-ash'}`} aria-live="polite">
                                {blockTime.startsWith('-') ? 'Check times' : blockTime}
                            </p>
                        </div>
                    </div>
                </fieldset>

                <fieldset className="card p-5 sm:p-6">
                    <legend className="sr-only">Route</legend>
                    <p className="eyebrow mb-5 text-clay">02 · Route</p>
                    <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                        {field('departure_airport', 'From', 'e.g. KSFO', { minLength: 3, maxLength: 4 })}
                        {field('arrival_airport', 'To', 'e.g. KLAX', { minLength: 3, maxLength: 4 })}
                        <div>
                            <label htmlFor="distance" className="field-label">Distance (nm)</label>
                            <input
                                type="number"
                                id="distance"
                                name="distance"
                                value={formData.distance}
                                onChange={handleChange}
                                required
                                min="0"
                                className="field-input font-mono"
                            />
                        </div>
                    </div>
                </fieldset>

                <fieldset className="card p-5 sm:p-6">
                    <legend className="sr-only">Aircraft</legend>
                    <p className="eyebrow mb-5 text-clay">03 · Aircraft</p>
                    <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                        {field('registration_number', 'Registration', 'e.g. N172SP')}
                        <div>
                            <label htmlFor="aircraft_condition" className="field-label">Condition</label>
                            <select
                                id="aircraft_condition"
                                name="aircraft_condition"
                                value={formData.aircraft_condition}
                                onChange={handleChange}
                                className="field-input"
                            >
                                {Object.entries(CONDITIONS).map(([value, { label }]) => (
                                    <option key={value} value={value}>{label}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <label
                        htmlFor="photo"
                        className="mt-5 flex cursor-pointer items-center gap-4 rounded-lg border border-dashed border-line px-4 py-4 transition-colors hover:border-moss/60 hover:bg-graphite/50 focus-within:border-moss"
                    >
                        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-graphite text-moss">
                            <CameraIcon className="h-5 w-5" />
                        </span>
                        <span className="min-w-0">
                            <span className="block text-sm text-bone">
                                {formData.photo ? formData.photo.name : 'Add a photo from this flight'}
                            </span>
                            <span className="block text-xs text-ash">
                                {formData.photo ? 'Click to choose a different image' : 'Optional · any image file'}
                            </span>
                        </span>
                        <input
                            type="file"
                            id="photo"
                            name="photo"
                            onChange={handleFileChange}
                            accept="image/*"
                            className="sr-only"
                        />
                    </label>
                </fieldset>

                <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                    <Link href="/flights" className="btn btn-ghost">
                        Cancel
                    </Link>
                    <button type="submit" className="btn btn-primary px-6">
                        Save to logbook
                    </button>
                </div>
            </form>
        </PageShell>
    );
}
