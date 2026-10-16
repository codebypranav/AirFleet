import Link from 'next/link';
import { CheckIcon } from '@/components/Icons';
import type { GroupBadge } from '@/types/flight';

export const KIND_LABELS = {
    airline: 'Airline', operator: 'Operator', school: 'Flight school', alliance: 'Alliance', community: 'Community',
} as const;
export const CREATABLE_KINDS = ['community', 'airline', 'operator', 'school'] as const;

export default function GroupBadges({ groups }: { groups: GroupBadge[] }) {
    return (
        <ul className="flex flex-wrap gap-2">
            {groups.map((g) => (
                <li key={g.slug}>
                    <Link
                        href={`/groups/${g.slug}`}
                        title={g.is_official ? `Official ${KIND_LABELS[g.kind].toLowerCase()}` : 'Community group'}
                        className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1 text-sm text-bone transition-colors hover:bg-graphite/50"
                    >
                        {g.is_official && <CheckIcon className="h-3.5 w-3.5 text-fern" />}
                        {g.name}
                    </Link>
                </li>
            ))}
        </ul>
    );
}
