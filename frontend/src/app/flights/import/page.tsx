"use client";

import { useState } from 'react';
import Link from 'next/link';
import { PageHeader, PageShell, Section } from '@/components/PageShell';
import { CheckIcon, UploadIcon } from '@/components/Icons';
import type { ImportResult } from '@/types/flight';
import { API_BASE, errorMessage, importFlights } from '@/utils/api';

const SOURCES: Record<ImportResult['source'], string> = {
    airfleet: 'an AirFleet CSV',
    foreflight: 'ForeFlight',
    logten: 'LogTen Pro',
    myflightbook: 'MyFlightbook',
    template: 'the import template',
};

export default function ImportPage() {
    const [file, setFile] = useState<File | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [result, setResult] = useState<ImportResult | null>(null);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) return;
        setBusy(true);
        setError('');
        setResult(null);
        try {
            setResult(await importFlights(file));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Import failed');
        } finally {
            setBusy(false);
        }
    };

    return (
        <PageShell>
            <PageHeader
                eyebrow="Logbook · Import"
                title="Import flights"
                description="Bring in a logbook from ForeFlight, LogTen Pro, MyFlightbook, a spreadsheet or an AirFleet CSV. Flights you already have are skipped."
            />

            <form onSubmit={submit} className="space-y-6 animate-rise">
                {error && <p className="alert-error" role="alert">{error}</p>}
                <label
                    htmlFor="file"
                    className="card flex cursor-pointer flex-col items-center gap-3 border-dashed px-6 py-12 text-center transition-colors hover:border-moss/60 focus-within:border-moss"
                >
                    <span className="flex h-12 w-12 items-center justify-center rounded-full bg-graphite text-moss">
                        <UploadIcon className="h-5 w-5" />
                    </span>
                    <span className="text-bone">{file ? file.name : 'Choose a logbook file'}</span>
                    <span className="text-xs text-ash">CSV, tab-delimited text or .xlsx, up to 5 MB</span>
                    <input id="file" type="file" accept=".csv,.txt,.tsv,.xlsx,text/csv" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                </label>
                <div className="flex justify-end gap-3">
                    <Link href="/flights" className="btn btn-ghost">Back to logbook</Link>
                    <button type="submit" className="btn btn-primary" disabled={!file || busy}>
                        {busy ? 'Importing…' : 'Import flights'}
                    </button>
                </div>
            </form>

            {result && (
                <Section title="Result">
                    <p className="flex items-center gap-2 text-bone" role="status">
                        <CheckIcon className="h-5 w-5 text-fern" />
                        Imported {result.created} flight{result.created === 1 ? '' : 's'} from {SOURCES[result.source]}.
                        {result.duplicates > 0 && ` ${result.duplicates} already in your logbook.`}
                    </p>
                    {result.skipped > 0 && (
                        <div className="mt-4">
                            <p className="text-sm text-clay">{result.skipped} row{result.skipped === 1 ? ' was' : 's were'} skipped:</p>
                            <ul className="mt-2 space-y-1 text-sm text-stone">
                                {result.errors.map((e) => (
                                    <li key={e.row}>
                                        <span className="font-mono text-ash">Row {e.row}:</span> {errorMessage(e.errors)}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    <Link href="/flights" className="btn btn-primary mt-6">See your logbook</Link>
                </Section>
            )}

            <Section title="Supported formats">
                <p className="mb-6 text-sm text-ash">
                    Slash dates are read as month/day, so if your app writes day/month export ISO dates (YYYY-MM-DD) instead.
                </p>
                <dl className="grid gap-6 text-sm md:grid-cols-2">
                    <div>
                        <dt className="text-bone">ForeFlight</dt>
                        <dd className="mt-1 text-ash">
                            In ForeFlight, go to Logbook → Settings → Export and choose CSV. Aircraft types come across with your flights.
                            Airports need ICAO codes; rows with local identifiers (like 1B9) are listed so you can add them by hand.
                        </dd>
                    </div>
                    <div>
                        <dt className="text-bone">LogTen Pro</dt>
                        <dd className="mt-1 text-ash">
                            In LogTen, run the Export Flights (Tab) exporter and upload the .txt file. Times are read as UTC.
                            Three-letter codes are read as IATA or US FAA codes (LHR becomes EGLL, PAE becomes KPAE); a code
                            that could mean either is listed for you to fix.
                        </dd>
                    </div>
                    <div>
                        <dt className="text-bone">MyFlightbook</dt>
                        <dd className="mt-1 text-ash">
                            On MyFlightbook, open Logbook → Download and save the CSV. The first and last airports in each route
                            become the departure and arrival, and the full route goes in the flight plan.
                        </dd>
                    </div>
                    <div>
                        <dt className="text-bone">Spreadsheet template</dt>
                        <dd className="mt-1 text-ash">
                            <a href={`${API_BASE}/flights/import/template/`} className="text-fern hover:underline">Download the template</a>,
                            fill in one flight per row and upload it as .xlsx or CSV. Durations can be 1.5 or 1:30; Time Off is UTC.
                        </dd>
                    </div>
                    <div>
                        <dt className="text-bone">AirFleet CSV</dt>
                        <dd className="mt-1 text-ash">
                            Use Export CSV on the logbook to see the columns. The minimum is departure_airport, arrival_airport,
                            departure_time, arrival_time and registration_number; times are ISO 8601, durations HH:MM:SS.
                        </dd>
                    </div>
                </dl>
            </Section>
        </PageShell>
    );
}
