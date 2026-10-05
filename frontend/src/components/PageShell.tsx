import Navbar from '@/components/Navbar';
import Contours from '@/components/Contours';

export function PageShell({ children }: { children: React.ReactNode }) {
    return (
        <div className="relative min-h-screen overflow-hidden bg-ink text-bone">
            <Contours className="absolute inset-x-0 top-0 h-[520px] w-full text-moss/10 [mask-image:linear-gradient(to_bottom,black,transparent)]" />
            <Navbar />
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
            <p className="relative font-display text-2xl text-paper">{title}</p>
            <div className="relative mt-3 max-w-sm text-sm text-stone">{children}</div>
        </div>
    );
}

export function Spinner({ label }: { label: string }) {
    return (
        <div className="flex flex-col items-center justify-center gap-4 py-24 text-ash" role="status">
            <div className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-moss" />
            <span className="eyebrow">{label}</span>
        </div>
    );
}
