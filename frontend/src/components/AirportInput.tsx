"use client";

import { useEffect, useId, useState } from 'react';
import type { Airport } from '@/types/flight';
import { getAirport, searchAirports } from '@/utils/api';

/** ICAO code field with suggestions; reports the matching airport (or null) as the code changes. */
export default function AirportInput({
    id,
    label,
    value,
    onChange,
    onResolve,
    required = true,
    placeholder,
}: {
    id: string;
    label: string;
    value: string;
    onChange: (code: string) => void;
    onResolve?: (airport: Airport | null) => void;
    required?: boolean;
    placeholder?: string;
}) {
    const listId = useId();
    const [suggestions, setSuggestions] = useState<Airport[]>([]);
    const [resolved, setResolved] = useState<{ code: string; airport: Airport | null } | null>(null);
    const code = value.trim().toUpperCase();

    useEffect(() => {
        if (code.length < 2) return;
        const timer = setTimeout(() => {
            searchAirports(code).then(setSuggestions).catch(() => setSuggestions([]));
        }, 200);
        return () => clearTimeout(timer);
    }, [code]);

    useEffect(() => {
        if (code.length !== 4) {
            onResolve?.(null);
            return;
        }
        let ignore = false;
        getAirport(code)
            .then((airport) => airport, () => null)
            .then((airport) => {
                if (ignore) return;
                setResolved({ code, airport });
                onResolve?.(airport);
            });
        return () => {
            ignore = true;
        };
        // onResolve is a callback prop; re-resolving on its identity would loop.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [code]);

    const match = resolved?.code === code ? resolved : null;
    const hint =
        code.length !== 4 ? 'ICAO code, e.g. KSFO' : !match ? 'Looking up…' : match.airport ? [match.airport.name, match.airport.city, match.airport.country].filter(Boolean).join(' · ') : 'Unknown airport code';

    return (
        <div>
            <label htmlFor={id} className="field-label">{label}</label>
            <input
                type="text"
                id={id}
                name={id}
                list={listId}
                value={value}
                onChange={(e) => onChange(e.target.value.toUpperCase().slice(0, 4))}
                required={required}
                minLength={4}
                maxLength={4}
                autoComplete="off"
                placeholder={placeholder}
                aria-describedby={`${id}-hint`}
                aria-invalid={Boolean(match && !match.airport)}
                className="field-input font-mono uppercase tracking-wider placeholder:normal-case placeholder:tracking-normal"
            />
            <datalist id={listId}>
                {code.length >= 2 && suggestions.map((a) => (
                    <option key={a.code} value={a.code}>{`${a.name}${a.city ? ` · ${a.city}` : ''}`}</option>
                ))}
            </datalist>
            <p id={`${id}-hint`} className={`mt-1.5 truncate text-xs ${match && !match.airport ? 'text-[#e7b6a1]' : 'text-ash'}`}>
                {hint}
            </p>
        </div>
    );
}
