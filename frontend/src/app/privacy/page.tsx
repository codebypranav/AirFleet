import type { Metadata } from 'next';
import { PageHeader, PageShell, Section } from '@/components/PageShell';

export const metadata: Metadata = { title: 'Privacy · AirFleet' };

// Set NEXT_PUBLIC_PRIVACY_CONTACT to the address that answers privacy requests.
const CONTACT = process.env.NEXT_PUBLIC_PRIVACY_CONTACT;

function Item({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <li>
            <span className="text-bone">{title}</span>
            <span className="text-stone"> — {children}</span>
        </li>
    );
}

export default function PrivacyPage() {
    return (
        <PageShell variant="public">
            <PageHeader
                eyebrow="Privacy"
                title="Your data in AirFleet"
                description="What the logbook stores, who else sees it, and how to get it back or erase it."
            />
            <div className="max-w-3xl space-y-4 text-sm leading-relaxed">
                <Section title="What we store">
                    <ul className="list-disc space-y-2 pl-5">
                        <Item title="Account">username, email, name, bio and home airport, plus a hashed password (never the password itself).</Item>
                        <Item title="Flights">airports, dates and times, aircraft registrations, logbook times, weather, notes, flight plans, photos and generated stories. Together these are a record of where and when you flew.</Item>
                        <Item title="Aircraft">registrations, types, hours and maintenance dates you enter.</Item>
                        <Item title="Cookies">only the sign-in tokens that keep you logged in. No advertising or tracking cookies.</Item>
                    </ul>
                </Section>

                <Section title="Why">
                    <p className="text-stone">
                        To run your logbook: keep your flights, work out totals, currency and rankings, and send you
                        password-reset emails. We don&apos;t sell your data or use it for advertising.
                    </p>
                </Section>

                <Section title="Who else handles it">
                    <ul className="list-disc space-y-2 pl-5">
                        <Item title="OpenAI">only when you ask for a story: the flight&apos;s airports, times, aircraft, weather, logbook times and the first 500 characters of your notes.</Item>
                        <Item title="Google">only if you sign in with Google, to confirm your email address.</Item>
                        <Item title="aviationweather.gov and SimBrief">when you fetch weather (airport code and date) or import a flight plan (your SimBrief username).</Item>
                        <Item title="Hosting">the app, database, photo storage and email are run by our hosting providers, who store data on our behalf.</Item>
                    </ul>
                </Section>

                <Section title="Public profiles">
                    <p className="text-stone">
                        Your logbook is private unless you turn on <em>Public profile</em>. Then anyone with the link can see
                        your profile, totals, route map and flights (route, times, aircraft, photo and story), which shows
                        where you have flown and when. Notes, gates and flight plans stay private. Your username and totals
                        appear in rankings either way.
                    </p>
                </Section>

                <Section title="Your choices">
                    <ul className="list-disc space-y-2 pl-5">
                        <Item title="See and correct">edit your profile and any flight at any time.</Item>
                        <Item title="Take it with you">export your logbook as CSV from the logbook page.</Item>
                        <Item title="Erase it">delete your account from your profile page. Your profile, flights, aircraft and photos are deleted straight away; database backups expire on their own shortly after.</Item>
                    </ul>
                    {CONTACT && (
                        <p className="mt-4 text-stone">
                            Questions or requests: <a href={`mailto:${CONTACT}`} className="text-fern hover:underline">{CONTACT}</a>.
                        </p>
                    )}
                </Section>

                <p className="pt-6 text-xs text-ash">
                    AirFleet is a personal logbook, not an official record-keeping system. As pilot, you remain responsible
                    for your own logbook under your aviation authority&apos;s rules.
                </p>
            </div>
        </PageShell>
    );
}
