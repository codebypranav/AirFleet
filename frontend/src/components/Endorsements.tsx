"use client";

import { useState } from 'react';
import { StatusPill, Withdrawn, WithdrawForm } from '@/components/Signature';
import type { Endorsement, EndorsementKind } from '@/types/flight';
import { getEndorsementKinds, giveEndorsement, withdrawEndorsement } from '@/utils/api';
import { formatDate } from '@/utils/format';
import { useApi } from '@/utils/useApi';

export const ENDORSEMENT_NOTE =
    'Endorsement drafts are plain-language starting points for the common US endorsements (the topics of AC 61-65), ' +
    "not the AC's wording. The instructor edits and is responsible for the text they sign.";

const today = () => {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
};

function validityLabel(kind: EndorsementKind) {
    if (!kind.validity) return 'Does not expire';
    const [unit, n] = kind.validity;
    return unit === 'days' ? `Lasts ${n} days` : `Lasts ${n} calendar months`;
}

export function EndorsementCard({ endorsement, onChange }: { endorsement: Endorsement; onChange?: (e: Endorsement) => void }) {
    const { status } = endorsement;
    return (
        <li className="card space-y-3 p-5 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                    <p className="font-display text-xl text-paper">{endorsement.title}</p>
                    {endorsement.regulation && <p className="mt-0.5 text-xs text-ash">{endorsement.regulation}</p>}
                </div>
                {status === 'current' && (
                    <StatusPill tone="good">{endorsement.expires_on ? `Current until ${formatDate(endorsement.expires_on)}` : 'Current'}</StatusPill>
                )}
                {status === 'expired' && <StatusPill tone="bad">Expired {formatDate(endorsement.expires_on!)}</StatusPill>}
                {status === 'withdrawn' && <StatusPill tone="muted">Withdrawn</StatusPill>}
            </div>
            <p className={`whitespace-pre-line ${status === 'withdrawn' ? 'text-ash line-through' : 'text-bone'}`}>{endorsement.text}</p>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div>
                    <dt className="eyebrow">Given</dt>
                    <dd className="mt-1 text-bone">{formatDate(endorsement.given_on)}</dd>
                </div>
                {endorsement.aircraft && (
                    <div>
                        <dt className="eyebrow">Aircraft</dt>
                        <dd className="mt-1 text-bone">{endorsement.aircraft}</dd>
                    </div>
                )}
                <div>
                    <dt className="eyebrow">Instructor</dt>
                    <dd className="mt-1 text-bone">{endorsement.instructor_name}</dd>
                </div>
                <div>
                    <dt className="eyebrow">Certificate</dt>
                    <dd className="mt-1 font-mono text-bone">
                        {endorsement.certificate_number}
                        {endorsement.certificate_expires && <span className="text-ash"> · exp. {endorsement.certificate_expires}</span>}
                    </dd>
                </div>
            </dl>
            {endorsement.withdrawn_at && <Withdrawn at={endorsement.withdrawn_at} reason={endorsement.withdrawal_reason} />}
            {endorsement.withdrawable && onChange && (
                <WithdrawForm what="endorsement" onWithdraw={async (data) => onChange(await withdrawEndorsement(endorsement.id, data))} />
            )}
        </li>
    );
}

const fill = (draft: string, student: string, aircraft: string) =>
    draft.replaceAll('{student}', student).replaceAll('{aircraft}', aircraft.trim() || '{aircraft}');

export function GiveEndorsementForm({ linkId, student, onGiven, onCancel }: {
    linkId: number | string;
    student: string;
    onGiven: (endorsement: Endorsement) => void;
    onCancel: () => void;
}) {
    const { data: kinds, error: loadError } = useApi(getEndorsementKinds);
    const [kind, setKind] = useState('');
    const [title, setTitle] = useState('');
    const [aircraft, setAircraft] = useState('');
    const [text, setText] = useState('');
    // Once the instructor edits the wording, changing the aircraft no longer rewrites it.
    const [edited, setEdited] = useState(false);
    const [givenOn, setGivenOn] = useState(today);
    const [agree, setAgree] = useState(false);
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);

    const chosen = kinds?.find((k) => k.kind === kind);

    const chooseKind = (value: string) => {
        setKind(value);
        setEdited(false);
        const next = kinds?.find((k) => k.kind === value);
        setText(next ? fill(next.draft, student, aircraft) : '');
    };
    const changeAircraft = (value: string) => {
        setAircraft(value);
        if (chosen && !edited) setText(fill(chosen.draft, student, value));
    };

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            onGiven(await giveEndorsement(linkId, { kind, title, text, aircraft, given_on: givenOn, agree, password }));
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not give the endorsement');
            setSaving(false);
        }
    };

    if (loadError) return <p className="alert-error" role="alert">{loadError}</p>;

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <div>
                    <label htmlFor="endorsement-kind" className="field-label">Endorsement</label>
                    <select id="endorsement-kind" value={kind} onChange={(e) => chooseKind(e.target.value)} required className="field-input">
                        <option value="" disabled>Choose one</option>
                        {kinds?.map((k) => (
                            <option key={k.kind} value={k.kind}>{k.title || 'Other (write your own)'}</option>
                        ))}
                    </select>
                    {chosen && chosen.kind !== 'other' && (
                        <p className="mt-1.5 text-xs text-ash">{chosen.regulation} · {validityLabel(chosen)}</p>
                    )}
                </div>
                <div>
                    <label htmlFor="endorsement-date" className="field-label">Date given</label>
                    <input id="endorsement-date" type="date" value={givenOn} max={today()} onChange={(e) => setGivenOn(e.target.value)} required className="field-input" />
                </div>
                {kind === 'other' && (
                    <div>
                        <label htmlFor="endorsement-title" className="field-label">Title</label>
                        <input id="endorsement-title" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={120} className="field-input" />
                    </div>
                )}
                <div>
                    <label htmlFor="endorsement-aircraft" className="field-label">
                        Aircraft make and model{chosen?.needs_aircraft ? '' : ' (optional)'}
                    </label>
                    <input id="endorsement-aircraft" value={aircraft} onChange={(e) => changeAircraft(e.target.value)} required={chosen?.needs_aircraft} maxLength={60} className="field-input" placeholder="e.g. Cessna 172" />
                </div>
            </div>
            {kind && (
                <>
                    <div>
                        <label htmlFor="endorsement-text" className="field-label">Wording</label>
                        <textarea
                            id="endorsement-text"
                            value={text}
                            onChange={(e) => {
                                setText(e.target.value);
                                setEdited(true);
                            }}
                            rows={4}
                            required
                            maxLength={2000}
                            className="field-input"
                        />
                        <p className="mt-1.5 text-xs text-ash">{ENDORSEMENT_NOTE}</p>
                    </div>
                    <label htmlFor="endorsement-agree" className="flex cursor-pointer items-start gap-3 rounded-lg border border-line px-4 py-3 transition-colors hover:border-ash/60">
                        <input type="checkbox" id="endorsement-agree" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-1 h-4 w-4 accent-[var(--color-moss)]" />
                        <span className="text-sm text-bone">I give this endorsement to {student}, and the wording above is correct.</span>
                    </label>
                    <div className="sm:w-72">
                        <label htmlFor="endorsement-password" className="field-label">Your password</label>
                        <input id="endorsement-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" className="field-input" />
                        <p className="mt-1.5 text-xs text-ash">Leave blank if you only sign in with Google.</p>
                    </div>
                </>
            )}
            <div className="flex justify-end gap-2">
                <button type="button" onClick={onCancel} className="btn btn-ghost">Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={saving || !kind || !agree}>
                    {saving ? 'Signing…' : 'Sign endorsement'}
                </button>
            </div>
        </form>
    );
}
