import Link from 'next/link';
import Contours from '@/components/Contours';
import { ArrowIcon } from '@/components/Icons';
import { CompassCard, Wordmark } from '@/components/Brand';

const FEATURES = [
    { n: '01', title: 'Log', body: 'Block time, route, tail number and the state of the airframe.' },
    { n: '02', title: 'Photograph', body: 'Keep a ramp shot from every leg, filed alongside the entry.' },
    { n: '03', title: 'Debrief', body: 'AI writes each flight up as a short story worth rereading.' },
];

export default function HomePage() {
    return (
      <main className="relative flex min-h-screen flex-col overflow-hidden bg-ink">
        <div
          className="photo-duotone absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: 'url("/home_bg.jpg")' }}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-ink via-ink/85 to-ink/30" />
        <div className="absolute inset-0 bg-gradient-to-t from-ink via-transparent to-ink/60" />
        <div className="absolute inset-0 bg-moss-deep/20 mix-blend-multiply" />
        <Contours className="absolute inset-0 h-full w-full text-sand/10" />
        <div className="pointer-events-none absolute -right-40 top-1/2 hidden aspect-square w-[720px] -translate-y-1/2 lg:block">
          <CompassCard className="h-full w-full text-bone/15 animate-[spin_240s_linear_infinite]" />
          <span className="absolute left-1/2 top-0 h-0 w-0 -translate-x-1/2 border-x-[9px] border-t-[16px] border-x-transparent border-t-clay/70" />
        </div>

        <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
          <Wordmark />
          <Link href="/register" className="text-sm text-stone transition-colors hover:text-paper">
            Create an account
          </Link>
        </header>

        <section className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-6 py-16">
          <p className="eyebrow mb-6 animate-rise">Pilot&apos;s logbook · for the hours that count</p>
          <h1 className="max-w-3xl font-display text-5xl font-light leading-[1.02] tracking-tight text-paper animate-rise [animation-delay:80ms] sm:text-7xl">
            Every flight, <em className="font-normal text-fern">written down.</em>
          </h1>
          <p className="mt-6 max-w-lg text-lg text-stone animate-rise [animation-delay:160ms]">
            Log every leg, keep the ramp photos, and get a debrief of each flight —
            a logbook built by and for people who fly.
          </p>
          <div className="mt-10 flex flex-wrap gap-3 animate-rise [animation-delay:240ms]">
            <Link href="/login" className="btn btn-primary px-6 py-3 text-base">
              Log in
              <ArrowIcon className="h-4 w-4" />
            </Link>
            <Link href="/register" className="btn btn-ghost bg-ink/40 px-6 py-3 text-base backdrop-blur-sm">
              Start a logbook
            </Link>
          </div>
        </section>

        <section className="relative z-10 border-t border-line/70 bg-ink/60 backdrop-blur-sm">
          <div className="mx-auto grid w-full max-w-6xl gap-px sm:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.n} className="px-6 py-7">
                <p className="font-mono text-xs text-clay">{f.n}</p>
                <p className="mt-2 font-display text-xl text-paper">{f.title}</p>
                <p className="mt-1 text-sm text-ash">{f.body}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    );
}
