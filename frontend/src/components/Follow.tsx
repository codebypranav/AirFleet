"use client";

import Avatar from '@/components/Avatar';
import { useAction } from '@/components/Crew';
import { Section } from '@/components/PageShell';
import type { PilotCard } from '@/types/flight';
import { approveFollower, blockPilot, followPilot, getFollows, getProfile, isLoggedIn, removeFollower, unblockPilot, unfollowPilot } from '@/utils/api';
import { useApi } from '@/utils/useApi';

export const countLabel = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`;

export function FollowButton({ username, onChange }: { username: string; onChange: () => void }) {
    const { data, reload } = useApi(
        () => (isLoggedIn() ? Promise.all([getFollows(), getProfile()]) : Promise.resolve(null)),
        `follow-${username}`,
    );
    const { busy, error, run } = useAction();
    if (!data || data[1].username === username) return null;
    const status = data[0].following.find((f) => f.username === username)?.status;
    const done = () => {
        reload();
        onChange();
    };

    return (
        <div className="flex flex-col items-end gap-2">
            {status ? (
                <button onClick={() => run(() => unfollowPilot(username).then(done))} disabled={busy} className="btn btn-ghost">
                    {status === 'APPROVED' ? 'Unfollow' : 'Cancel request'}
                </button>
            ) : (
                <button onClick={() => run(() => followPilot(username).then(done))} disabled={busy} className="btn btn-primary">Follow</button>
            )}
            {error && <p className="alert-error" role="alert">{error}</p>}
        </div>
    );
}

type Action = [label: string, act: (username: string) => Promise<unknown>];

export function PilotList({ pilots, actions, onDone, empty, note }: {
    pilots: (PilotCard & { status?: string })[];
    actions: Action[];
    onDone: () => void;
    empty?: string;
    note?: (pilot: PilotCard & { status?: string }) => string | undefined;
}) {
    const { busy, error, run } = useAction();
    if (!pilots.length) return <p className="text-sm text-ash">{empty}</p>;
    return (
        <>
            <ul className="space-y-3">
                {pilots.map((pilot) => (
                    <li key={pilot.username} className="flex items-center gap-3 text-sm">
                        <Avatar username={pilot.username} avatar={pilot.avatar} />
                        <p className="min-w-0 flex-1 text-bone">
                            {pilot.username}
                            {note?.(pilot) && <span className="text-ash"> · {note(pilot)}</span>}
                        </p>
                        {actions.map(([label, act]) => (
                            <button key={label} onClick={() => run(() => act(pilot.username).then(onDone))} disabled={busy} className="btn btn-ghost py-1.5 text-sm">
                                {label}
                            </button>
                        ))}
                    </li>
                ))}
            </ul>
            {error && <p className="alert-error mt-3" role="alert">{error}</p>}
        </>
    );
}

export function FollowersSection() {
    const { data: follows, reload } = useApi(getFollows, 'follows');
    if (!follows) return null;
    const following = follows.following.filter((f) => f.status === 'APPROVED').length;
    return (
        <>
            {follows.requests.length > 0 && (
                <Section title="Follow requests">
                    <PilotList pilots={follows.requests} actions={[['Approve', approveFollower], ['Deny', removeFollower]]} onDone={reload} />
                </Section>
            )}
            <Section title={`Followers · ${countLabel(follows.followers.length, 'follower')}, following ${following.toLocaleString()}`}>
                <PilotList
                    pilots={follows.followers}
                    actions={[['Remove', removeFollower], ['Block', blockPilot]]}
                    onDone={reload}
                    empty="No followers yet. Followers see your flights in the air and your logged flights."
                />
            </Section>
            {follows.blocked.length > 0 && (
                <Section title="Blocked pilots">
                    <PilotList pilots={follows.blocked} actions={[['Unblock', unblockPilot]]} onDone={reload} />
                </Section>
            )}
        </>
    );
}
