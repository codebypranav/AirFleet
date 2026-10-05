"use client";

import { useState } from 'react';
import type { Aircraft } from '@/types/flight';
import { AIRCRAFT_CLASSES } from '@/utils/format';

type Fields = Pick<Aircraft, 'registration' | 'type_code' | 'make_model' | 'aircraft_class' | 'notes' | 'maintenance_interval_hours' | 'annual_due'>;

export default function AircraftForm({
    aircraft,
    submitLabel,
    onSubmit,
    onCancel,
}: {
    aircraft?: Aircraft;
    submitLabel: string;
    onSubmit: (data: Partial<Aircraft>) => Promise<void>;
    onCancel?: () => void;
}) {
    const [form, setForm] = useState<Fields>({
        registration: aircraft?.registration ?? '',
        type_code: aircraft?.type_code ?? '',
        make_model: aircraft?.make_model ?? '',
        aircraft_class: aircraft?.aircraft_class ?? 'SEL',
        notes: aircraft?.notes ?? '',
        maintenance_interval_hours: aircraft?.maintenance_interval_hours ?? 100,
        annual_due: aircraft?.annual_due ?? null,
    });
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);

    const change = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
        setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            await onSubmit({
                ...form,
                registration: form.registration.trim().toUpperCase(),
                type_code: form.type_code.trim().toUpperCase(),
                maintenance_interval_hours: Number(form.maintenance_interval_hours) || 100,
                annual_due: form.annual_due || null,
            });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not save the aircraft');
        } finally {
            setSaving(false);
        }
    };

    const prefix = aircraft ? `aircraft-${aircraft.id}` : 'new-aircraft';

    return (
        <form onSubmit={submit} className="card space-y-5 p-5 sm:p-6">
            {error && <p className="alert-error" role="alert">{error}</p>}
            <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                <div>
                    <label htmlFor={`${prefix}-registration`} className="field-label">Registration</label>
                    <input id={`${prefix}-registration`} name="registration" value={form.registration} onChange={change} required maxLength={10} placeholder="e.g. N172SP" className="field-input font-mono uppercase" />
                </div>
                <div>
                    <label htmlFor={`${prefix}-type`} className="field-label">ICAO type</label>
                    <input id={`${prefix}-type`} name="type_code" value={form.type_code} onChange={change} maxLength={4} placeholder="e.g. C172" className="field-input font-mono uppercase" />
                </div>
                <div>
                    <label htmlFor={`${prefix}-make`} className="field-label">Make &amp; model</label>
                    <input id={`${prefix}-make`} name="make_model" value={form.make_model} onChange={change} maxLength={60} placeholder="e.g. Cessna 172S" className="field-input" />
                </div>
                <div>
                    <label htmlFor={`${prefix}-class`} className="field-label">Class</label>
                    <select id={`${prefix}-class`} name="aircraft_class" value={form.aircraft_class} onChange={change} className="field-input">
                        {Object.entries(AIRCRAFT_CLASSES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                </div>
                <div>
                    <label htmlFor={`${prefix}-interval`} className="field-label">Inspection every (hours)</label>
                    <input id={`${prefix}-interval`} name="maintenance_interval_hours" type="number" min="1" value={form.maintenance_interval_hours} onChange={change} className="field-input font-mono" />
                </div>
                <div>
                    <label htmlFor={`${prefix}-annual`} className="field-label">Annual due</label>
                    <input id={`${prefix}-annual`} name="annual_due" type="date" value={form.annual_due ?? ''} onChange={change} className="field-input" />
                </div>
            </div>
            <div>
                <label htmlFor={`${prefix}-notes`} className="field-label">Notes</label>
                <textarea id={`${prefix}-notes`} name="notes" value={form.notes} onChange={change} rows={2} className="field-input" />
            </div>
            <div className="flex justify-end gap-3">
                {onCancel && <button type="button" onClick={onCancel} className="btn btn-ghost">Cancel</button>}
                <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : submitLabel}</button>
            </div>
        </form>
    );
}

/** Status pill and inspection progress shared by the fleet list and the aircraft page. */
export function maintenanceStatus(aircraft: Aircraft, today = new Date()) {
    const annualDays = aircraft.annual_due ? Math.ceil((new Date(aircraft.annual_due).getTime() - today.getTime()) / 86400000) : null;
    if (aircraft.grounded) return { label: 'Grounded', tone: 'border-rust/50 bg-rust/15 text-[#e7b6a1]', annualDays };
    if (aircraft.maintenance_due) return { label: 'Inspection due', tone: 'border-clay/50 bg-clay/15 text-clay', annualDays };
    if (annualDays !== null && annualDays < 0) return { label: 'Annual overdue', tone: 'border-rust/50 bg-rust/15 text-[#e7b6a1]', annualDays };
    if (annualDays !== null && annualDays <= 30) return { label: `Annual in ${annualDays} d`, tone: 'border-sand/40 bg-sand/10 text-sand', annualDays };
    return { label: 'Airworthy', tone: 'border-moss/50 bg-moss/15 text-fern', annualDays };
}

export function InspectionBar({ aircraft }: { aircraft: Aircraft }) {
    const share = Math.min(aircraft.hours_since_maintenance / aircraft.maintenance_interval_hours, 1);
    return (
        <div>
            <div className="flex items-baseline justify-between text-xs">
                <span className="eyebrow">Since inspection</span>
                <span className="font-mono text-stone">
                    {aircraft.hours_since_maintenance} / {aircraft.maintenance_interval_hours} h
                </span>
            </div>
            <div
                className="mt-2 h-1.5 overflow-hidden rounded-full bg-graphite"
                role="meter"
                aria-label="Hours since last inspection"
                aria-valuemin={0}
                aria-valuemax={aircraft.maintenance_interval_hours}
                aria-valuenow={aircraft.hours_since_maintenance}
            >
                <div className={`h-full rounded-full ${share >= 1 ? 'bg-rust' : share >= 0.85 ? 'bg-clay' : 'bg-moss'}`} style={{ width: `${share * 100}%` }} />
            </div>
        </div>
    );
}
