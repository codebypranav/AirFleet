"use client";

import { useId, useState } from 'react';
import type { Signature } from '@/types/flight';
import { withdrawSignature } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { AlertIcon, CheckIcon } from '@/components/Icons';

const FIELD_LABELS: Record<string, string> = {
    departure_airport: 'Departure airport',
    arrival_airport: 'Arrival airport',
    departure_time: 'Departure time',
    arrival_time: 'Arrival time',
    total_time: 'Block time',
    registration_number: 'Aircraft',
    pic_time: 'PIC',
    sic_time: 'SIC',
    dual_received_time: 'Dual received',
    night_time: 'Night',
    instrument_time: 'Actual instrument',
    simulated_instrument_time: 'Simulated instrument',
    day_landings: 'Day landings',
    night_landings: 'Night landings',
    approaches: 'Approaches',
    cross_country: 'Cross-country',
    is_simulator: 'Simulator',
};

export const DISCLAIMER =
    "Instructor-verified means a linked instructor confirmed this entry in AirFleet. It isn't a certified " +
    'electronic signature for 14 CFR 61.51(h) or any other rule.';

const GOOD = 'border-moss/60 text-fern';
const BAD = 'border-rust/60 text-[#e7b6a1]';
const MUTED = 'border-line text-ash';

export function StatusPill({ tone, children }: { tone: 'good' | 'bad' | 'muted'; children: React.ReactNode }) {
    const className = { good: GOOD, bad: BAD, muted: MUTED }[tone];
    return (
        <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs ${className}`}>
            {tone === 'good' ? <CheckIcon className="h-3 w-3" /> : <AlertIcon className="h-3 w-3" />}
            {children}
        </span>
    );
}

export function SignatureBadge({ signature }: { signature: Signature | null }) {
    if (!signature) return null;
    if (signature.status === 'valid') return <StatusPill tone="good">Instructor-verified</StatusPill>;
    if (signature.status === 'withdrawn') return <StatusPill tone="muted">Signature withdrawn</StatusPill>;
    return <StatusPill tone="bad">Signature invalidated</StatusPill>;
}

/** Shown when an instructor withdrew a signature or endorsement. */
export function Withdrawn({ at, reason }: { at: string; reason: string }) {
    return (
        <p className="rounded-lg border border-line bg-graphite/50 px-4 py-3 text-stone">
            Withdrawn by the instructor on {formatDate(at, 'long')}{reason ? `: ${reason}` : '.'}
        </p>
    );
}

/** Lets the instructor who gave a signature or endorsement take it back, with a reason and their password. */
export function WithdrawForm({ what, onWithdraw }: { what: string; onWithdraw: (data: { reason: string; password: string }) => Promise<void> }) {
    const [open, setOpen] = useState(false);
    const [reason, setReason] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const id = useId();

    if (!open) {
        return (
            <div className="flex justify-end">
                <button type="button" onClick={() => setOpen(true)} className="btn btn-ghost px-3 py-1 text-xs hover:border-rust/60 hover:text-[#e7b6a1]">
                    Withdraw {what}
                </button>
            </div>
        );
    }

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setBusy(true);
        setError('');
        try {
            await onWithdraw({ reason, password });
        } catch (err) {
            setError(err instanceof Error ? err.message : `Could not withdraw the ${what}`);
            setBusy(false);
        }
    };

    return (
        <form onSubmit={submit} className="space-y-4 border-t border-dashed border-line pt-4">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <p className="text-stone">The student will see that you withdrew it, when, and your reason. The record isn&apos;t deleted.</p>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                    <label htmlFor={`${id}-reason`} className="field-label">Reason</label>
                    <input id={`${id}-reason`} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={1000} className="field-input" placeholder="e.g. Signed the wrong lesson" />
                </div>
                <div>
                    <label htmlFor={`${id}-password`} className="field-label">Your password</label>
                    <input id={`${id}-password`} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="field-input" />
                    <p className="mt-1.5 text-xs text-ash">Leave blank if you only sign in with Google.</p>
                </div>
            </div>
            <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setOpen(false)} className="btn btn-ghost">Cancel</button>
                <button type="submit" disabled={busy} className="btn btn-ghost text-rust">{busy ? 'Withdrawing…' : `Withdraw ${what}`}</button>
            </div>
        </form>
    );
}

export function SignatureDetails({ signature, viewer, onChange }: {
    signature: Signature;
    viewer: 'student' | 'instructor';
    onChange?: (signature: Signature) => void;
}) {
    const { status } = signature;
    return (
        <div className={`card space-y-3 p-5 text-sm ${status === 'invalidated' ? 'border-rust/50' : ''}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <SignatureBadge signature={signature} />
                <span className="eyebrow">Signed {formatDate(signature.signed_at, 'long')}</span>
            </div>
            <p className={status === 'withdrawn' ? 'text-ash line-through' : 'text-bone'}>{signature.statement}</p>
            <dl className="grid grid-cols-2 gap-4">
                <div>
                    <dt className="eyebrow">Instructor</dt>
                    <dd className="mt-1 text-bone">{signature.instructor_name}</dd>
                </div>
                <div>
                    <dt className="eyebrow">Certificate</dt>
                    <dd className="mt-1 font-mono text-bone">
                        {signature.certificate_number}
                        {signature.certificate_expires && <span className="text-ash"> · exp. {signature.certificate_expires}</span>}
                    </dd>
                </div>
            </dl>
            {signature.remarks && <p className="whitespace-pre-line text-stone">&ldquo;{signature.remarks}&rdquo;</p>}
            {signature.withdrawn_at && <Withdrawn at={signature.withdrawn_at} reason={signature.withdrawal_reason} />}
            {status === 'invalidated' && (
                <p className="alert-error">
                    Changed since signing: {signature.changed_fields.map((f) => FIELD_LABELS[f] ?? f).join(', ')}.{' '}
                    {viewer === 'student'
                        ? 'Ask your instructor to sign it again, or change it back.'
                        : 'Check the entry and sign it again if it is right.'}
                </p>
            )}
            {status === 'withdrawn' && viewer === 'student' && (
                <p className="text-ash">Ask your instructor if you need this lesson signed again.</p>
            )}
            {signature.withdrawable && onChange && (
                <WithdrawForm what="signature" onWithdraw={async (data) => onChange(await withdrawSignature(signature.id, data))} />
            )}
        </div>
    );
}
