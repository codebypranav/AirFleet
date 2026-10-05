// The API returns a full signed URL when photos live in object storage,
// and a /media/... path when they're on the backend's local disk.
export const photoUrl = (photo: string) =>
    /^https?:\/\//.test(photo) ? photo : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${photo}`;

// DRF serializes durations as "[D ]HH:MM:SS[.ffffff]"; str(timedelta) on the
// rankings endpoint gives "[D day[s], ]H:MM:SS".
export const durationToSeconds = (value?: string) => {
    const match = value?.match(/^(?:(\d+)(?: days?,)? )?(\d+):(\d{2}):(\d{2})/);
    if (!match) return 0;
    const [, days = '0', h, m, s] = match;
    return Number(days) * 86400 + Number(h) * 3600 + Number(m) * 60 + Number(s);
};

export const formatHours = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return `${h}h ${m.toString().padStart(2, '0')}m`;
};

export const formatDuration = (value?: string) => {
    const seconds = durationToSeconds(value);
    return seconds ? formatHours(seconds) : value || '—';
};

export const CONDITIONS: Record<string, { label: string; className: string }> = {
    AIRWORTHY: { label: 'Airworthy', className: 'border-moss/50 bg-moss/15 text-fern' },
    GOOD: { label: 'Good condition', className: 'border-fern/40 bg-fern/10 text-fern' },
    MINOR_ISSUES: { label: 'Minor issues', className: 'border-sand/40 bg-sand/10 text-sand' },
    MAINTENANCE: { label: 'Needs maintenance', className: 'border-clay/50 bg-clay/15 text-clay' },
    GROUNDED: { label: 'Grounded', className: 'border-rust/50 bg-rust/15 text-[#e7b6a1]' },
};

export const conditionFor = (value: string) =>
    CONDITIONS[value] ?? { label: value, className: 'border-line bg-graphite text-stone' };
