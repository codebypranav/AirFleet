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
