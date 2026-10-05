import type { Achievement, Currency, Stats } from '@/types/flight';
import { AlertIcon, CheckIcon, MedalIcon } from '@/components/Icons';
import { formatDate } from '@/utils/format';

const niceMax = (value: number) => {
    if (value <= 0) return 1;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= value) ?? 10;
    return step * magnitude;
};

const monthLabel = (iso: string, month: 'short' | 'long' = 'short') =>
    new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month, ...(month === 'long' ? { year: 'numeric' } : {}) });

/** Hours flown per month for the last 12 months: one series, columns from a shared baseline. */
export function MonthlyHoursChart({ months }: { months: Stats['by_month'] }) {
    const max = niceMax(Math.max(...months.map((m) => m.hours)));
    const peak = months.reduce((best, m, i) => (m.hours > months[best].hours ? i : best), 0);
    const ticks = [max, max / 2, 0];

    return (
        <figure>
            <div className="relative flex h-56 gap-2 pl-10">
                {ticks.map((tick) => (
                    <div
                        key={tick}
                        className="pointer-events-none absolute left-10 right-0 border-t border-line"
                        style={{ bottom: `${(tick / max) * 100}%` }}
                    >
                        <span className="absolute -left-10 -translate-y-1/2 font-mono text-[0.65rem] text-ash">{tick.toLocaleString()}</span>
                    </div>
                ))}
                {months.map((m, i) => (
                    <div key={m.month} className="group relative flex flex-1 flex-col items-center justify-end" tabIndex={0} aria-label={`${monthLabel(m.month, 'long')}: ${m.hours} hours, ${m.flights} flights`}>
                        {i === peak && m.hours > 0 && (
                            <span className="mb-1 font-mono text-[0.7rem] text-stone">{m.hours}</span>
                        )}
                        <div
                            className="w-full max-w-6 rounded-t bg-moss transition-colors group-hover:bg-fern group-focus-visible:bg-fern"
                            style={{ height: `${(m.hours / max) * 100}%`, minHeight: m.hours > 0 ? 2 : 0 }}
                        />
                        <div className="pointer-events-none absolute bottom-full z-10 mb-2 hidden whitespace-nowrap rounded-lg border border-line bg-graphite px-3 py-2 text-xs text-bone shadow-lg group-hover:block group-focus-visible:block">
                            <p className="eyebrow mb-1">{monthLabel(m.month, 'long')}</p>
                            <p>{m.hours} h · {m.flights} flight{m.flights === 1 ? '' : 's'}</p>
                            <p className="text-ash">{m.distance.toLocaleString()} nm</p>
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-2 flex gap-2 pl-10" aria-hidden="true">
                {months.map((m) => (
                    <span key={m.month} className="flex-1 text-center font-mono text-[0.65rem] uppercase text-ash">{monthLabel(m.month).slice(0, 3)}</span>
                ))}
            </div>
            <figcaption className="mt-3 text-xs text-ash">Hours flown per month, last 12 months.</figcaption>
            <details className="mt-3 text-sm">
                <summary className="cursor-pointer text-xs text-fern">Show as a table</summary>
                <table className="mt-3 w-full text-left text-sm">
                    <thead className="eyebrow">
                        <tr><th className="py-1 font-normal">Month</th><th className="py-1 text-right font-normal">Flights</th><th className="py-1 text-right font-normal">Hours</th><th className="py-1 text-right font-normal">Distance</th></tr>
                    </thead>
                    <tbody className="text-bone">
                        {months.map((m) => (
                            <tr key={m.month} className="border-t border-line">
                                <td className="py-1">{monthLabel(m.month, 'long')}</td>
                                <td className="py-1 text-right font-mono">{m.flights}</td>
                                <td className="py-1 text-right font-mono">{m.hours}</td>
                                <td className="py-1 text-right font-mono">{m.distance.toLocaleString()} nm</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </details>
        </figure>
    );
}

/** A ranked list with a thin bar showing each row's share of the top value. */
export function RankedList({ rows, empty }: { rows: { key: string; label: React.ReactNode; detail: string; value: number }[]; empty: string }) {
    if (rows.length === 0) return <p className="text-sm text-ash">{empty}</p>;
    const max = Math.max(...rows.map((r) => r.value), 1);
    return (
        <ol className="space-y-3">
            {rows.map((row) => (
                <li key={row.key}>
                    <div className="flex items-baseline justify-between gap-4 text-sm">
                        <span className="truncate text-bone">{row.label}</span>
                        <span className="shrink-0 font-mono text-stone">{row.detail}</span>
                    </div>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-graphite">
                        <div className="h-full rounded-full bg-moss" style={{ width: `${(row.value / max) * 100}%` }} />
                    </div>
                </li>
            ))}
        </ol>
    );
}

const CURRENCY_TONES = {
    current: { label: 'Current', className: 'border-moss/50 text-fern', Icon: CheckIcon },
    expiring: { label: 'Expiring soon', className: 'border-sand/50 text-sand', Icon: AlertIcon },
    lapsed: { label: 'Not current', className: 'border-rust/50 text-[#e7b6a1]', Icon: AlertIcon },
};

export function CurrencyCards({ items }: { items: Currency[] }) {
    return (
        <ul className="grid gap-4 md:grid-cols-3">
            {items.map((item) => {
                const tone = CURRENCY_TONES[item.status];
                return (
                    <li key={item.key} className="card p-5">
                        <div className="flex items-start justify-between gap-3">
                            <p className="text-bone">{item.label}</p>
                            <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${tone.className}`}>
                                <tone.Icon className="h-3.5 w-3.5" />
                                {tone.label}
                            </span>
                        </div>
                        <p className="mt-3 text-sm text-stone">
                            {item.expires_on && item.status !== 'lapsed'
                                ? `Until ${formatDate(item.expires_on)} (${item.days_left} day${item.days_left === 1 ? '' : 's'})`
                                : item.expires_on
                                    ? `Lapsed ${formatDate(item.expires_on)}`
                                    : 'Never current yet'}
                        </p>
                        <p className="mt-1 text-xs text-ash">{item.rule}. {item.count_in_window} in that window now.</p>
                    </li>
                );
            })}
        </ul>
    );
}

export function AchievementGrid({ items }: { items: Achievement[] }) {
    return (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {items.map((a) => (
                <li
                    key={a.key}
                    className={`card flex flex-col items-center gap-2 px-3 py-5 text-center ${a.earned ? '' : 'opacity-45'}`}
                    title={a.description}
                >
                    <MedalIcon className={`h-8 w-8 ${a.earned ? 'text-clay' : 'text-ash'}`} />
                    <p className="text-sm text-bone">{a.title}</p>
                    <p className="text-xs text-ash">{a.earned && a.earned_at ? formatDate(a.earned_at) : a.description}</p>
                    <span className="sr-only">{a.earned ? 'Earned' : 'Not earned yet'}</span>
                </li>
            ))}
        </ul>
    );
}
