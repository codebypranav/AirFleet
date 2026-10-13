import Image from 'next/image';
import { photoUrl } from '@/utils/format';

export default function Avatar({ username, avatar, size = 36 }: { username: string; avatar: string | null; size?: number }) {
    if (avatar) {
        return (
            <Image
                src={photoUrl(avatar)}
                alt={username}
                width={size}
                height={size}
                unoptimized
                className="shrink-0 rounded-full border border-line object-cover"
                style={{ width: size, height: size }}
            />
        );
    }
    return (
        <span
            role="img"
            aria-label={username}
            className="inline-flex shrink-0 items-center justify-center rounded-full border border-line bg-graphite font-medium uppercase text-stone"
            style={{ width: size, height: size, fontSize: size * 0.4 }}
        >
            {username.slice(0, 2)}
        </span>
    );
}
