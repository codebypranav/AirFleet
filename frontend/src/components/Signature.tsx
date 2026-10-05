import type { Signature } from '@/types/flight';
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

export function SignatureBadge({ signature }: { signature: Signature | null }) {
    if (!signature) return null;
    return signature.status === 'valid' ? (
        <span className="inline-flex items-center gap-1 rounded-full border border-moss/60 px-2.5 py-0.5 text-xs text-fern">
            <CheckIcon className="h-3 w-3" />
            Instructor-verified
        </span>
    ) : (
        <span className="inline-flex items-center gap-1 rounded-full border border-rust/60 px-2.5 py-0.5 text-xs text-[#e7b6a1]">
            <AlertIcon className="h-3 w-3" />
            Signature invalidated
        </span>
    );
}

export function SignatureDetails({ signature, viewer }: { signature: Signature; viewer: 'student' | 'instructor' }) {
    const valid = signature.status === 'valid';
    return (
        <div className={`card space-y-3 p-5 text-sm ${valid ? '' : 'border-rust/50'}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <SignatureBadge signature={signature} />
                <span className="eyebrow">Signed {formatDate(signature.signed_at, 'long')}</span>
            </div>
            <p className="text-bone">{signature.statement}</p>
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
            {!valid && (
                <p className="alert-error">
                    Changed since signing: {signature.changed_fields.map((f) => FIELD_LABELS[f] ?? f).join(', ')}.{' '}
                    {viewer === 'student'
                        ? 'Ask your instructor to sign it again, or change it back.'
                        : 'Check the entry and sign it again if it is right.'}
                </p>
            )}
        </div>
    );
}
