"use client";

import { useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';
import type { Airport, RouteMapData } from '@/types/flight';
import { greatCircle } from '@/utils/format';

// Read the palette from the theme so the map follows globals.css.
const token = (name: string, fallback: string) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

/** Great-circle route map. Lines get heavier the more often a route was flown. */
export default function RouteMap({ data, className = 'h-80' }: { data: RouteMapData; className?: string }) {
    const container = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const element = container.current;
        if (!element || data.airports.length === 0) return;
        let map: import('leaflet').Map | null = null;
        let cancelled = false;

        import('leaflet').then((L) => {
            if (cancelled) return;
            const moss = token('--color-moss', '#7d9459');
            const fern = token('--color-fern', '#a8bb82');
            const ink = token('--color-ink', '#11120f');

            map = L.map(element, { worldCopyJump: true, scrollWheelZoom: false, attributionControl: true });
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 12,
            }).addTo(map);

            const byCode = new Map<string, Airport>(data.airports.map((a) => [a.code, a]));
            const most = Math.max(...data.routes.map((r) => r.flights), 1);
            const bounds = L.latLngBounds([]);

            for (const route of data.routes) {
                const from = byCode.get(route.from);
                const to = byCode.get(route.to);
                if (!from || !to) continue;
                const points = greatCircle(from, to);
                points.forEach((p) => bounds.extend(p));
                L.polyline(points, {
                    color: moss,
                    weight: 1.5 + 2.5 * (route.flights / most),
                    opacity: 0.85,
                    lineCap: 'round',
                })
                    .bindTooltip(`${route.from} → ${route.to} · ${route.flights} flight${route.flights === 1 ? '' : 's'} · ${route.hours} h`, { sticky: true })
                    .addTo(map);
            }

            for (const airport of data.airports) {
                bounds.extend([airport.lat, airport.lon]);
                L.circleMarker([airport.lat, airport.lon], {
                    radius: 5,
                    color: ink,
                    weight: 2,
                    fillColor: fern,
                    fillOpacity: 1,
                })
                    .bindTooltip(`<strong>${airport.code}</strong> · ${airport.name}`, { direction: 'top', offset: [0, -4] })
                    .addTo(map);
            }

            if (bounds.isValid()) {
                map.fitBounds(bounds, { padding: [32, 32], maxZoom: 8 });
            } else {
                map.setView([20, 0], 2);
            }
        });

        return () => {
            cancelled = true;
            map?.remove();
        };
    }, [data]);

    if (data.airports.length === 0) {
        return (
            <div className={`card flex items-center justify-center text-sm text-ash ${className}`}>
                Routes you fly will be drawn here.
            </div>
        );
    }

    return (
        <div
            ref={container}
            className={`route-map overflow-hidden rounded-xl border border-line ${className}`}
            role="img"
            aria-label={`Map of ${data.routes.length} route${data.routes.length === 1 ? '' : 's'} between ${data.airports.length} airports`}
        />
    );
}
