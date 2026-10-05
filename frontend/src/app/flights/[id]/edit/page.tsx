"use client";

import { use } from 'react';
import { useRouter } from 'next/navigation';
import FlightForm from '@/components/FlightForm';
import { AlertIcon } from '@/components/Icons';
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
                <>
                {flight.signature?.status === 'valid' && (
                    <p className="mb-6 flex items-start gap-2 rounded-lg border border-clay/50 px-4 py-3 text-sm text-sand" role="note">
                        <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
                        {flight.signature.instructor_name} signed this entry. Changing the route, times, aircraft, logbook columns,
                        landings or approaches will invalidate the signature. Notes and photos are fine to change.
                    </p>
                )}
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
                </>
            )}
        </PageShell>
    );
}
