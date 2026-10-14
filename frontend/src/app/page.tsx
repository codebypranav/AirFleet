import Image from 'next/image';
import Link from 'next/link';
import Contours from '@/components/Contours';
import { ArrowIcon } from '@/components/Icons';
import { CompassCard, Wordmark } from '@/components/Brand';

const FEATURES = [
    {
        title: 'Logbook and stats',
        body: 'Log every standard column, with ICAO codes checked as you type. Stats show your totals, currency, achievements and a map of every route you have flown.',
        image: 'stats',
    },
    {
        title: 'Quick log and flight plans',
        body: 'Describe a flight in your own words and AI fills in the form, or drop in a SimBrief OFP to start a draft with the route, times and tail number already read.',
        image: 'flight-plan',
    },
    {
        title: 'Plan review and patterns',
        body: "Before you go, AirFleet checks a draft against your own logbook: block time, daylight, currency on the day, a new airport and the aircraft's maintenance. Patterns flag a long gap since your last flight, skills unused for months and maintenance coming due.",
        image: 'plan-review',
    },
    {
        title: 'Live flights and crew',
        body: 'Start a flight and your crew and followers see it in the air until you land. Each crewmate you invite gets a copy in their own logbook, credited to their seat.',
        image: 'live',
    },
    {
        title: 'Following, comments and likes',
        body: 'Follow other pilots for a feed of their flights. Like a leg, leave a comment, and see replies from the bell in the nav.',
        image: 'feed',
    },
    {
        title: 'Instructor sign-off',
        body: 'Link with your instructor to get lessons signed and endorsements given in the app. Each endorsement shows whether it is current and when it runs out.',
        image: 'instruction',
    },
];

export default function HomePage() {
    return (
      <main className="bg-ink">
        <div className="relative flex min-h-screen flex-col overflow-hidden bg-ink">
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
            <Wordmark size="lg" />
            <Link href="/register" className="text-sm text-stone transition-colors hover:text-paper">
              Create an account
            </Link>
          </header>

          <section className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-6 py-16">
            <p className="eyebrow mb-6 animate-rise">Pilot&apos;s logbook</p>
            <h1 className="max-w-3xl font-display text-5xl font-light leading-[1.02] tracking-tight text-paper animate-rise [animation-delay:80ms] sm:text-7xl">
              Every flight, <em className="font-normal text-fern">in one place.</em>
            </h1>
            <p className="mt-6 max-w-lg text-lg text-stone animate-rise [animation-delay:160ms]">
              Log each leg, fly with your crew, and check your next flight
              against your own logbook.
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
        </div>

        <div className="mx-auto w-full max-w-6xl space-y-24 border-t border-line/70 px-6 py-24">
          {FEATURES.map((f, i) => (
            <section key={f.image} aria-labelledby={`feature-${f.image}`} className="grid items-center gap-8 lg:grid-cols-5 lg:gap-12">
              <div className={`lg:col-span-2 ${i % 2 ? 'lg:order-last' : ''}`}>
                <p className="font-mono text-xs text-clay">{String(i + 1).padStart(2, '0')}</p>
                <h2 id={`feature-${f.image}`} className="mt-2 font-display text-3xl font-light text-paper">{f.title}</h2>
                <p className="mt-3 text-stone">{f.body}</p>
              </div>
              <Image
                src={`/landing/${f.image}.jpg`}
                alt={`AirFleet: ${f.title.toLowerCase()}`}
                width={1440}
                height={900}
                sizes="(min-width: 1024px) 680px, 100vw"
                className="rounded-lg border border-line shadow-2xl lg:col-span-3"
              />
            </section>
          ))}
          <p className="border-t border-line/70 pt-10 text-sm text-ash">
            Also: CSV import from ForeFlight and export, METAR and SimBrief lookups, a photo from every leg,
            rankings and public pilot pages.
          </p>
        </div>
      </main>
    );
}
