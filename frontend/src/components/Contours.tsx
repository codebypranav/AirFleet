// Decorative topographic contour lines. Paths are generated from pure math at
// module load, so server and client render identical markup.

type Peak = { cx: number; cy: number; rings: number; step: number; seed: number };

const ringPath = ({ cx, cy, step, seed }: Peak, k: number) => {
    const points: string[] = [];
    const n = 96;
    for (let i = 0; i <= n; i++) {
        const t = (i / n) * Math.PI * 2;
        const wobble =
            1 +
            0.14 * Math.sin(3 * t + seed + k * 0.35) +
            0.08 * Math.sin(5 * t - seed * 1.7 + k * 0.2) +
            0.04 * Math.sin(9 * t + k);
        const r = step * (k + 1) * wobble;
        const x = cx + r * Math.cos(t) * 1.25;
        const y = cy + r * Math.sin(t);
        points.push(`${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    return points.join('') + 'Z';
};

const PEAKS: Peak[] = [
    { cx: 260, cy: 210, rings: 14, step: 22, seed: 0.6 },
    { cx: 930, cy: 520, rings: 16, step: 24, seed: 2.1 },
    { cx: 1180, cy: 90, rings: 7, step: 20, seed: 4.2 },
];

const PATHS = PEAKS.flatMap((peak) =>
    Array.from({ length: peak.rings }, (_, k) => ({ d: ringPath(peak, k), index: k })),
);

export default function Contours({ className = '' }: { className?: string }) {
    return (
        <svg
            aria-hidden="true"
            viewBox="0 0 1200 700"
            preserveAspectRatio="xMidYMid slice"
            className={`pointer-events-none ${className}`}
            fill="none"
            stroke="currentColor"
        >
            {PATHS.map(({ d, index }, i) => (
                <path key={i} d={d} strokeWidth={index % 5 === 4 ? 1.4 : 0.7} />
            ))}
        </svg>
    );
}
