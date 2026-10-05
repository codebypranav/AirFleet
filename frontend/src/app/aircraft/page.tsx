"use client";

import { useState } from 'react';
import Link from 'next/link';
import AircraftForm, { ForecastNote, InspectionBar, maintenanceStatus } from '@/components/AircraftForm';
import { PlusIcon } from '@/components/Icons';
import { EmptyState, ErrorState, PageHeader, PageShell, Spinner } from '@/components/PageShell';
import { addAircraft, getFleet } from '@/utils/api';
import { AIRCRAFT_CLASSES, formatDuration } from '@/utils/format';
import { useApi } from '@/utils/useApi';

export default function FleetPage() {
    const { data: fleet, error, reload } = useApi(getFleet);
    const [adding, setAdding] = useState(false);

    return (
        <PageShell>
            <PageHeader
                eyebrow="Fleet"
                title="My aircraft"
                description="Every airframe in your logbook, with hours and inspection status. New registrations are added when you log a flight."
                action={
                    !adding && (
                        <button onClick={() => setAdding(true)} className="btn btn-primary">
                            <PlusIcon className="h-4 w-4" />
                            Add aircraft
                        </button>
                    )
                }
            />

            {adding && (
                <div className="mb-8 animate-rise">
                    <AircraftForm
                        submitLabel="Add to fleet"
                        onCancel={() => setAdding(false)}
                        onSubmit={async (data) => {
                            await addAircraft(data);
                            setAdding(false);
                            reload();
                        }}
                    />
                </div>
            )}

            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !fleet ? (
                <Spinner label="Walking the ramp" />
            ) : fleet.length === 0 ? (
                <EmptyState title="An empty hangar">
                    <p>Add an aircraft, or log a flight and its registration will appear here.</p>
                </EmptyState>
            ) : (
                <ul className="grid gap-4 md:grid-cols-2">
                    {fleet.map((plane, i) => {
                        const status = maintenanceStatus(plane);
                        return (
                            <li key={plane.id} className="animate-rise" style={{ animationDelay: `${Math.min(i, 8) * 50}ms` }}>
                                <Link href={`/aircraft/${plane.id}`} className="card flex h-full flex-col gap-5 p-5 transition-colors hover:border-ash/50 sm:p-6">
                                    <div className="flex items-start justify-between gap-3">
                                        <div>
                                            <p className="font-mono text-2xl font-medium tracking-wider text-paper">{plane.registration}</p>
                                            <p className="mt-1 text-sm text-ash">
                                                {[plane.type_code, plane.make_model].filter(Boolean).join(' · ') || AIRCRAFT_CLASSES[plane.aircraft_class]}
                                            </p>
                                        </div>
                                        <span className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs ${status.tone}`}>{status.label}</span>
                                    </div>
                                    <dl className="grid grid-cols-2 gap-4 border-t border-dashed border-line pt-4 text-sm">
                                        <div>
                                            <dt className="eyebrow">Flights</dt>
                                            <dd className="mt-1 text-bone">{plane.total_flights}</dd>
                                        </div>
                                        <div>
                                            <dt className="eyebrow">Total time</dt>
                                            <dd className="mt-1 text-bone">{formatDuration(plane.total_time)}</dd>
                                        </div>
                                    </dl>
                                    <div className="space-y-2">
                                        <InspectionBar aircraft={plane} />
                                        <ForecastNote aircraft={plane} compact />
                                    </div>
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            )}
        </PageShell>
    );
}
