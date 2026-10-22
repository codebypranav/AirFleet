"use client";

import Link from 'next/link';
import { EmptyState, ErrorState, PageHeader, PageShell, Section, Spinner } from '@/components/PageShell';
import { StatusPill } from '@/components/Signature';
import type { StudentProgress } from '@/types/flight';
import { getInstructorDashboard } from '@/utils/api';
import { formatDay } from '@/utils/format';
import { useApi } from '@/utils/useApi';

function StudentCard({ progress }: { progress: StudentProgress }) {
    const { student, hours, endorsements, missing } = progress;
    return (
        <li className="card space-y-5 p-5 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="font-display text-xl text-paper">
                    {student.name}
                    {student.name !== student.username && <span className="text-sm text-ash"> · {student.username}</span>}
                </h2>
                <Link href={`/instruction/students/${progress.link_id}`} className="btn btn-ghost">Lessons</Link>
            </div>

            {missing.length === 0 ? (
                <StatusPill tone="good">Meets the 61.109(a) minimums on record</StatusPill>
            ) : (
                <div>
                    <h3 className="eyebrow mb-2">Missing</h3>
                    <ul className="list-disc space-y-1 pl-5 text-bone">
                        {missing.map((m) => <li key={m}>{m}</li>)}
                    </ul>
                </div>
            )}

            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead className="text-xs text-ash">
                        <tr><th className="py-1 font-normal">Requirement</th><th className="py-1 text-right font-normal">Logged / needed</th></tr>
                    </thead>
                    <tbody>
                        {hours.map((row) => (
                            <tr key={row.key} className="border-t border-line">
                                <td className="py-2 pr-4">
                                    <span className="text-bone">{row.label}</span>
                                    <span className="text-xs text-ash"> · {row.regulation}</span>
                                    {row.signed !== undefined && <span className="text-xs text-ash"> · signed {row.signed} h</span>}
                                </td>
                                <td className={`py-2 text-right font-mono ${row.short ? 'text-stone' : 'text-bone'}`}>
                                    {row.have} / {row.need}{row.unit && ` ${row.unit}`}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div>
                <h3 className="eyebrow mb-2">Endorsements</h3>
                <ul className="flex flex-wrap gap-2">
                    {endorsements.map((e) => (
                        <li key={e.kind} title={e.regulation}>
                            <StatusPill tone={e.status === 'current' ? 'good' : e.status === 'expired' ? 'bad' : 'muted'}>
                                {e.title}
                                {e.status === 'expired' && ` · expired ${formatDay(e.expires_on!)}`}
                                {e.status === 'missing' && ' · missing'}
                            </StatusPill>
                        </li>
                    ))}
                </ul>
            </div>
        </li>
    );
}

export default function InstructorDashboardPage() {
    const { data, error, reload } = useApi(getInstructorDashboard);

    return (
        <PageShell>
            <PageHeader
                eyebrow="Instruction"
                title="Student progress"
                description="Each linked student's logged flights, simulator sessions left out, measured against the private pilot minimums for airplane single-engine land in 14 CFR 61.109(a). It is a guide, not a checkride sign-off."
            />
            {error ? (
                <ErrorState message={error} onRetry={reload} />
            ) : !data ? (
                <Spinner label="Adding up your students' hours" />
            ) : data.students.length === 0 ? (
                <EmptyState title="No linked students">
                    <p>When a student links with you, their progress shows up here.</p>
                </EmptyState>
            ) : (
                <>
                    <ul className="space-y-6">
                        {data.students.map((s) => <StudentCard key={s.link_id} progress={s} />)}
                    </ul>
                    <Section title="Check the logbook for">
                        <ul className="list-disc space-y-1 pl-5 text-sm text-stone">
                            {data.checks.map((c) => <li key={c.regulation}>{c.label} <span className="text-ash">· {c.regulation}</span></li>)}
                        </ul>
                        <p className="mt-3 text-xs text-ash">
                            Solo counts PIC time on flights with no dual received. Dual night and dual simulated instrument count the
                            smaller of that time and the dual on each flight.
                        </p>
                    </Section>
                </>
            )}
        </PageShell>
    );
}
