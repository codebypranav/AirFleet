type IconProps = { className?: string };

export function PlaneIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} fill="currentColor">
            <path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5Z" />
        </svg>
    );
}

export function PlusIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
        </svg>
    );
}

export function ArrowIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12h14M13 6l6 6-6 6" />
        </svg>
    );
}

export function CameraIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
            <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
            <circle cx="12" cy="13" r="3.5" />
        </svg>
    );
}

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round' } as const;

export function EditIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4" />
        </svg>
    );
}

export function TrashIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
        </svg>
    );
}

export function DownloadIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />
        </svg>
    );
}

export function UploadIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M12 16V5M7 10l5-5 5 5M5 20h14" />
        </svg>
    );
}

export function ShareIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M14 5h5v5M19 5l-8 8M17 14v5H5V7h5" />
        </svg>
    );
}

export function CloudIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M7 18h10a4 4 0 0 0 .5-7.97A6 6 0 0 0 6 9.5 4.25 4.25 0 0 0 7 18Z" />
        </svg>
    );
}

export function WrenchIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M15 4a5 5 0 0 0-4.6 6.9L4 17.3V20h2.7l6.4-6.4A5 5 0 0 0 20 9l-3 3-3-1-1-3 3-3a5 5 0 0 0-1-1Z" />
        </svg>
    );
}

export function CheckIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke} strokeWidth={2}>
            <path d="m5 12 4.5 4.5L19 7" />
        </svg>
    );
}

export function AlertIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M12 4 2.5 20h19L12 4ZM12 10v4M12 17h.01" />
        </svg>
    );
}

export function MedalIcon({ className = '' }: IconProps) {
    return (
        <svg aria-hidden="true" viewBox="0 0 24 24" className={className} {...stroke}>
            <path d="M8 3h8l-2 6h-4L8 3Z" />
            <circle cx="12" cy="15" r="5" />
            <path d="m12 12.5.8 1.6 1.7.2-1.2 1.2.3 1.7-1.6-.8-1.6.8.3-1.7-1.2-1.2 1.7-.2.8-1.6Z" />
        </svg>
    );
}
