import Navbar from '@/components/Navbar';
import Contours from '@/components/Contours';
import { CompassCard } from '@/components/Brand';

export function PageShell({ children, variant = 'app' }: { children: React.ReactNode; variant?: 'app' | 'public' }) {
    return (
        <div className="relative min-h-screen overflow-hidden bg-ink text-bone">
            <Contours className="absolute inset-x-0 top-0 h-[520px] w-full text-moss/10 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
            <Navbar variant={variant} />
            <main className="relative mx-auto w-full max-w-5xl px-4 pb-24 pt-10 sm:px-6 sm:pt-14">{children}</main>
        </div>
    );
}

export function PageHeader({
    eyebrow,
    title,
    description,
    action,
}: {
    eyebrow: string;
    title: string;
    description?: string;
    action?: React.ReactNode;
}) {
    return (
        <header className="mb-10 flex flex-col gap-6 border-b border-line pb-8 sm:flex-row sm:items-end sm:justify-between animate-rise">
            <div>
                <p className="eyebrow mb-3">{eyebrow}</p>
                <h1 className="font-display text-4xl font-medium tracking-tight text-paper sm:text-5xl">{title}</h1>
                {description && <p className="mt-3 max-w-xl text-stone">{description}</p>}
            </div>
            {action && <div className="shrink-0">{action}</div>}
        </header>
    );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
    return (
        <div className="card flex flex-col items-center overflow-hidden px-6 py-16 text-center">
            <Contours className="absolute inset-0 h-full w-full text-ash/10" />
            <CompassCard className="relative mb-6 h-32 w-32 text-moss/80" />
            <p className="relative font-display text-2xl text-paper">{title}</p>
            <div className="relative mt-3 max-w-sm text-sm text-stone">{children}</div>
        </div>
    );
}

export function Spinner({ label }: { label: string }) {
    return (
        <div className="flex flex-col items-center justify-center gap-4 py-24 text-ash" role="status">
            <div className="relative h-14 w-14">
                <CompassCard className="h-full w-full animate-[spin_6s_linear_infinite] text-moss" />
                <span className="absolute left-1/2 top-0 h-0 w-0 -translate-x-1/2 border-x-[4px] border-t-[7px] border-x-transparent border-t-clay" />
            </div>
            <span className="eyebrow">{label}</span>
        </div>
    );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
    return (
        <div className="alert-error flex flex-wrap items-center justify-between gap-3" role="alert">
            <span>{message}</span>
            {onRetry && (
                <button onClick={onRetry} className="btn btn-ghost px-3 py-1 text-xs">
                    Try again
                </button>
            )}
        </div>
    );
}

/** A labelled figure in the logbook's stat strip. */
export function StatGrid({ stats }: { stats: { label: string; value: string }[] }) {
    return (
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4 animate-rise">
            {stats.map((stat) => (
                <div key={stat.label} className="bg-char px-5 py-4">
                    <dt className="eyebrow">{stat.label}</dt>
                    <dd className="mt-1 font-display text-2xl text-paper sm:text-3xl">{stat.value}</dd>
                </div>
            ))}
        </dl>
    );
}

export function Section({ title, action, children, className = '' }: { title: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
    return (
        <section className={`mt-12 animate-rise ${className}`}>
            <div className="mb-4 flex items-end justify-between gap-4 border-b border-dashed border-line pb-3">
                <h2 className="eyebrow text-clay">{title}</h2>
                {action}
            </div>
            {children}
        </section>
    );
}
