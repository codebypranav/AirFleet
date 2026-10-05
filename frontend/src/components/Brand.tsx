// AirFleet's mark: a compass dial whose maple leaf midrib is the needle.

const MAPLE_LEAF =
    'M50 6 55 17 61 14 58 36 70 24 73 30 85 27 81 40 87 43 70 57 73 64 53 61 52.5 80 47.5 80 47 61 27 64 30 57 13 43 19 40 15 27 27 30 30 24 42 36 39 14 45 17Z';

const polar = (cx: number, cy: number, r: number, deg: number) => {
    const rad = ((deg - 90) * Math.PI) / 180;
    return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)].map((n) => n.toFixed(2));
};

export function MapleLeaf({ className = '' }: { className?: string }) {
    return (
        <svg aria-hidden="true" viewBox="0 0 100 100" className={className} fill="currentColor">
            <path d={MAPLE_LEAF} strokeLinejoin="round" />
        </svg>
    );
}

// Palmate veins fanning out from the leaf's centre (50 43), in MAPLE_LEAF coordinates.
const LEAF_VEINS =
    'M50 43 77 31M50 43 23 31M50 43 66 55M50 43 34 55M50 43 50 62M64 37 67 28M36 37 33 28M68 35 80 41M32 35 20 41M50 33 56 22M50 33 44 22';

// Centre the leaf's bounding box (13–87 × 6–80) on the dial's pivot at (24, 24).
const LEAF_SCALE = 0.42;
const LEAF_TRANSFORM = `translate(${24 - 50 * LEAF_SCALE} ${24 - 43 * LEAF_SCALE}) scale(${LEAF_SCALE})`;

export function BrandMark({ className = '' }: { className?: string }) {
    // No tick at north: the needle marks it.
    const ticks = Array.from({ length: 11 }, (_, i) => (i + 1) * 30);
    return (
        <svg aria-hidden="true" viewBox="0 0 48 48" className={className} fill="none">
            <circle cx="24" cy="24" r="21" stroke="currentColor" strokeOpacity="0.7" strokeWidth="1.6" />
            {ticks.map((deg) => {
                const [x1, y1] = polar(24, 24, 21, deg);
                const [x2, y2] = polar(24, 24, deg % 90 === 0 ? 17.5 : 18.5, deg);
                return <line key={deg} x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />;
            })}
            <g transform={LEAF_TRANSFORM}>
                <path d={MAPLE_LEAF} fill="currentColor" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
                <path d={LEAF_VEINS} className="stroke-ink" strokeWidth="2.6" strokeLinecap="round" />
            </g>
            {/* The midrib doubles as the compass needle, pivoting at the leaf's centre and pointing north. */}
            <path d="M24 24V9.5" className="stroke-clay" strokeWidth="1.3" strokeLinecap="round" />
            <path d="M24 4.4 26 10H22Z" className="fill-clay stroke-clay" strokeWidth="0.5" strokeLinejoin="round" />
            <circle cx="24" cy="24" r="1.8" className="fill-clay stroke-ink" strokeWidth="0.7" />
        </svg>
    );
}

const WORDMARK_SIZES = {
    md: { gap: 'gap-3', mark: 'h-11 w-11', text: 'text-2xl' },
    lg: { gap: 'gap-3.5', mark: 'h-14 w-14', text: 'text-3xl' },
    xl: { gap: 'gap-5', mark: 'h-24 w-24', text: 'text-6xl' },
};

export function Wordmark({ size = 'md', className = '' }: { size?: keyof typeof WORDMARK_SIZES; className?: string }) {
    const s = WORDMARK_SIZES[size];
    return (
        <span className={`group flex items-center ${s.gap} ${className}`}>
            <BrandMark className={`${s.mark} shrink-0 text-fern transition-colors group-hover:text-sand`} />
            <span className={`font-display ${s.text} font-medium tracking-tight text-paper`}>AirFleet</span>
        </span>
    );
}

const CARDINALS: Record<number, string> = { 0: 'N', 90: 'E', 180: 'S', 270: 'W' };

// A full heading-indicator compass card, used as large decorative artwork.
export function CompassCard({ className = '' }: { className?: string }) {
    const ticks = Array.from({ length: 72 }, (_, i) => i * 5);
    return (
        <svg aria-hidden="true" viewBox="0 0 400 400" className={`pointer-events-none ${className}`} fill="none">
            <circle cx="200" cy="200" r="196" stroke="currentColor" strokeOpacity="0.5" />
            <circle cx="200" cy="200" r="120" stroke="currentColor" strokeOpacity="0.25" strokeDasharray="2 6" />
            {ticks.map((deg) => {
                const len = deg % 30 === 0 ? 22 : deg % 10 === 0 ? 14 : 8;
                const [x1, y1] = polar(200, 200, 190, deg);
                const [x2, y2] = polar(200, 200, 190 - len, deg);
                return (
                    <line
                        key={deg}
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke="currentColor"
                        strokeWidth={deg % 30 === 0 ? 2 : 1}
                    />
                );
            })}
            {ticks
                .filter((deg) => deg % 30 === 0)
                .map((deg) => {
                    const [x, y] = polar(200, 200, 150, deg);
                    return (
                        <text
                            key={deg}
                            x={x}
                            y={y}
                            transform={`rotate(${deg} ${x} ${y})`}
                            textAnchor="middle"
                            dominantBaseline="central"
                            fill="currentColor"
                            className="font-mono"
                            fontSize={CARDINALS[deg] ? 22 : 16}
                        >
                            {CARDINALS[deg] ?? deg / 10}
                        </text>
                    );
                })}
        </svg>
    );
}
