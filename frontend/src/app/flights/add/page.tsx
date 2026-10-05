"use client";

import { useRouter } from 'next/navigation';
import FlightForm from '@/components/FlightForm';
import { PageShell, PageHeader } from '@/components/PageShell';
import { addFlight } from '@/utils/api';

export default function AddFlight() {
    const router = useRouter();

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook · New entry"
                title="Add a flight"
                description="Fill in the leg as you'd write it in the paper log. Block time and distance are worked out for you."
            />
            <FlightForm
                submitLabel="Save to logbook"
                cancelHref="/flights"
                onSubmit={async (data) => {
                    const flight = await addFlight(data);
                    router.push(`/flights/${flight.id}`);
                }}
            />
        </PageShell>
    );
}
