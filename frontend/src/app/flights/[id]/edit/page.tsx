"use client";

import { use } from 'react';
import { useRouter } from 'next/navigation';
import FlightForm from '@/components/FlightForm';
import { ErrorState, PageHeader, PageShell, Spinner } from '@/components/PageShell';
import { getFlight, updateFlight } from '@/utils/api';
import { useApi } from '@/utils/useApi';

export default function EditFlight({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const { data: flight, error, reload } = useApi(() => getFlight(id), id);

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook · Edit entry"
                title={flight ? `${flight.departure_airport} → ${flight.arrival_airport}` : 'Edit flight'}
                description="Change anything about this leg. Leave the distance blank to recompute it."
            />
            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !flight ? (
                <Spinner label="Opening the entry" />
            ) : (
                <FlightForm
                    key={flight.id}
                    flight={flight}
                    submitLabel="Save changes"
                    cancelHref={`/flights/${flight.id}`}
                    onSubmit={async (data) => {
                        await updateFlight(flight.id, data);
                        router.push(`/flights/${flight.id}`);
                    }}
                />
            )}
        </PageShell>
    );
}
