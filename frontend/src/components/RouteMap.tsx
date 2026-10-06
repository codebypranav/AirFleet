"use client";

import { useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';
import type { Airport, RouteMapData } from '@/types/flight';
import { greatCircle } from '@/utils/format';

// Read the palette from the theme so the map follows globals.css.
const token = (name: string, fallback: string) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

// With an ArcGIS Location Platform key (free tier: 2M tiles a month) satellite view uses Esri's
// high-resolution World Imagery; without one it falls back to NASA's keyless Blue Marble mosaic.
const ARCGIS_KEY = process.env.NEXT_PUBLIC_ARCGIS_API_KEY;
const BASEMAP_KEY = 'airfleet.basemap';

const readBasemap = () => {
    try {
        return window.localStorage.getItem(BASEMAP_KEY);
    } catch {
        return null;
    }
};
const saveBasemap = (name: string) => {
    try {
        window.localStorage.setItem(BASEMAP_KEY, name);
    } catch {
        // Storage blocked: the choice just isn't remembered.
    }
};

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
            const basemaps: Record<string, import('leaflet').TileLayer> = {
                Map: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                    subdomains: 'abcd',
                    maxZoom: 12,
                }),
                Satellite: ARCGIS_KEY
                    ? L.tileLayer(`https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${encodeURIComponent(ARCGIS_KEY)}`, {
                          attribution: 'Powered by <a href="https://www.esri.com">Esri</a> &middot; Esri, Maxar, Earthstar Geographics, and the GIS User Community',
                          maxZoom: 12,
                      })
                    : L.tileLayer('https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg', {
                          attribution: 'Imagery &copy; <a href="https://www.earthdata.nasa.gov/gibs">NASA GIBS</a> Blue Marble',
                          maxNativeZoom: 8,
                          maxZoom: 12,
                      }),
            };
            const saved = readBasemap();
            basemaps[saved && saved in basemaps ? saved : 'Map'].addTo(map);
            L.control.layers(basemaps, undefined, { position: 'topright' }).addTo(map);
            map.on('baselayerchange', (e) => saveBasemap(e.name));

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
