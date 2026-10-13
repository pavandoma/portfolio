import { activityWeeks, parseDay, type Stats } from "@/lib/learning-stats";

/**
 * Hand-drawn SVG charts — no chart library. Every colour is a CSS variable, so
 * they follow the dark/light theme with no redraw. Sized by viewBox, so they
 * scale with the layout.
 */

/** A progress ring for one track: the arc is the share finished. */
export function Ring({ percent, label, done, total }: { percent: number; label: string; done: number; total: number }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  return (
    <figure className="flex flex-col items-center gap-3 text-center">
      <svg
        viewBox="0 0 100 100"
        className="size-28"
        role="img"
        aria-label={`${label}: ${done} of ${total} finished, ${percent} percent`}
      >
        <circle cx="50" cy="50" r={radius} fill="none" stroke="var(--hairline)" strokeWidth="3" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="var(--lit)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - percent / 100)}
          transform="rotate(-90 50 50)"
          className="transition-[stroke-dashoffset] duration-700 ease-out motion-reduce:transition-none"
        />
        <text
          x="50"
          y="54"
          textAnchor="middle"
          className="fill-foreground font-sans text-[22px] font-light"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {percent}
          <tspan className="fill-muted text-[10px]">%</tspan>
        </text>
      </svg>
      <figcaption>
        <span className="block font-mono text-[11px] tracking-[0.2em] uppercase text-foreground">{label}</span>
        <span className="mt-1 block font-mono text-[10px] tracking-[0.18em] text-muted tabular-nums">
          {done} / {total}
        </span>
      </figcaption>
    </figure>
  );
}

const shortDate = (day: string) =>
  parseDay(day).toLocaleDateString("en-US", { month: "short", day: "numeric" });

/** Steps finished, accumulated day by day. The line only ever climbs. */
export function CumulativeChart({ series, total }: { series: Stats["cumulative"]; total: number }) {
  const W = 640;
  const H = 220;
  const pad = { l: 36, r: 8, t: 12, b: 28 };
  const innerW = W - pad.l - pad.r;
  const innerH = H - pad.t - pad.b;
  const n = series.length;
  const x = (i: number) => pad.l + (n <= 1 ? innerW : (i / (n - 1)) * innerW);
  const y = (count: number) => pad.t + innerH - (total ? (count / total) * innerH : 0);

  // Stepped, because work finishes in whole steps, not gradually.
  let line = "";
  series.forEach((point, i) => {
    line += i === 0 ? `M${x(i)},${y(point.count)}` : ` H${x(i)} V${y(point.count)}`;
  });
  const area = `${line} V${pad.t + innerH} H${pad.l} Z`;
  const last = series[n - 1]?.count ?? 0;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={`Steps finished over time: ${last} of ${total}`}
    >
      {[0, 0.5, 1].map((fraction) => (
        <g key={fraction}>
          <line x1={pad.l} x2={W - pad.r} y1={y(total * fraction)} y2={y(total * fraction)} stroke="var(--hairline)" strokeWidth="1" />
          <text x={pad.l - 8} y={y(total * fraction) + 3} textAnchor="end" className="fill-muted font-mono text-[9px]">
            {Math.round(total * fraction)}
          </text>
        </g>
      ))}
      <path d={area} fill="var(--lit)" opacity="0.1" />
      <path d={line} fill="none" stroke="var(--lit)" strokeWidth="1.6" strokeLinejoin="round" />
      {n > 0 && <circle cx={x(n - 1)} cy={y(last)} r="3" fill="var(--lit)" />}
      <text x={pad.l} y={H - 8} className="fill-muted font-mono text-[9px]">
        {series[0] ? shortDate(series[0].day) : ""}
      </text>
      <text x={W - pad.r} y={H - 8} textAnchor="end" className="fill-muted font-mono text-[9px]">
        {series[n - 1] ? shortDate(series[n - 1].day) : ""}
      </text>
    </svg>
  );
}

/** One square per day for twenty weeks; brighter means more steps that day. */
export function ActivityGrid({ perDay }: { perDay: Stats["perDay"] }) {
  const weeks = activityWeeks(perDay);
  const cell = 12;
  const gap = 3;
  const W = weeks.length * (cell + gap) - gap;
  const H = 7 * (cell + gap) - gap;
  const max = Math.max(1, ...Object.values(perDay));
  const total = Object.values(perDay).reduce((a, b) => a + b, 0);

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full max-w-md"
      role="img"
      aria-label={`Activity over the last twenty weeks: ${total} steps finished`}
    >
      {weeks.map((column, w) =>
        column.map((day, d) =>
          day.future ? null : (
            <rect
              key={day.day}
              x={w * (cell + gap)}
              y={d * (cell + gap)}
              width={cell}
              height={cell}
              rx="2"
              fill={day.count ? "var(--lit)" : "var(--hairline)"}
              opacity={day.count ? 0.3 + 0.7 * (day.count / max) : 1}
            >
              <title>{`${shortDate(day.day)}: ${day.count} ${day.count === 1 ? "step" : "steps"}`}</title>
            </rect>
          ),
        ),
      )}
    </svg>
  );
}
