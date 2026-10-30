import type { Metadata } from 'next';
import { flightCardUrl, getPublicFlight } from '@/utils/api';
import { MILESTONES } from '@/utils/format';

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
    const { id } = await params;
    const flight = await getPublicFlight(id).catch(() => null);
    if (!flight) return { title: 'Shared flight · AirFleet' };
    const route = `${flight.departure_airport} → ${flight.arrival_airport}`;
    const headline = MILESTONES[flight.milestone] ?? route;
    const description = flight.milestone ? `${route} · ${flight.pilot}` : `Flown by ${flight.pilot}`;
    const images = [{ url: flightCardUrl(flight.id), width: 1080, height: 1350 }];
    return {
        title: `${headline} · AirFleet`,
        description,
        openGraph: { title: headline, description, images },
        twitter: { card: 'summary_large_image', title: headline, description, images },
    };
}

export default function SharedFlightLayout({ children }: { children: React.ReactNode }) {
    return children;
}
