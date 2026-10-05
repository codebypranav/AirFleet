import Link from 'next/link';
import Contours from '@/components/Contours';
import { Wordmark } from '@/components/Brand';

export default function AuthLayout({
    eyebrow,
    title,
    children,
}: {
    eyebrow: string;
    title: string;
    children: React.ReactNode;
}) {
    return (
        <main className="relative grid min-h-screen bg-ink lg:grid-cols-[1.1fr_1fr]">
            <aside className="relative hidden overflow-hidden border-r border-line lg:block">
                <div
                    className="photo-duotone absolute inset-0 bg-cover bg-center"
                    style={{ backgroundImage: 'url("/home_bg.jpg")' }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-ink via-ink/30 to-ink/50" />
                <div className="absolute inset-0 bg-moss-deep/25 mix-blend-multiply" />
                <Contours className="absolute inset-0 h-full w-full text-sand/10" />
                <div className="relative flex h-full flex-col justify-end p-12">
                    <Link href="/" className="self-start">
                        <Wordmark size="xl" />
                    </Link>
                    <p className="eyebrow mt-5 text-stone">Pilot&apos;s logbook</p>
                </div>
            </aside>

            <section className="relative flex items-center justify-center overflow-hidden px-4 py-12 sm:px-8">
                <Contours className="absolute inset-0 h-full w-full text-moss/[0.07]" />
                <div className="relative w-full max-w-sm animate-rise">
                    <Link href="/" className="mb-10 inline-block lg:hidden">
                        <Wordmark size="lg" />
                    </Link>
                    <p className="eyebrow mb-3">{eyebrow}</p>
                    <h1 className="mb-8 font-display text-4xl font-medium tracking-tight text-paper">{title}</h1>
                    {children}
                </div>
            </section>
        </main>
    );
}
