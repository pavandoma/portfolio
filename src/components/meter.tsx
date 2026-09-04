"use client";

import { motion, useReducedMotion } from "motion/react";
import type { Meter as MeterData } from "@/content/profile";
import { DURATION, EASE_OUT as EASE } from "@/lib/motion";

const VIEWPORT = { once: true, amount: 0.5 };
const SEGMENTS = 24;

/**
 * Segmented meter for a project's headline figure.
 *
 * A "ratio" fills a proportion of a fixed track; a "count" draws exactly that
 * many segments with no track, so a bare count can't read as 100%. The figure
 * is always printed as text — the bar never carries meaning on its own.
 */
export function Meter({ meter, delay = 0 }: { meter: MeterData; delay?: number }) {
  const reduceMotion = useReducedMotion();

  const total = meter.kind === "ratio" ? SEGMENTS : meter.segments;
  const filled =
    meter.kind === "ratio" ? Math.round(meter.fill * SEGMENTS) : meter.segments;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="eyebrow text-muted-foreground">{meter.label}</span>
        <span className="font-serif text-lg leading-none tabular-nums">
          {meter.display}
        </span>
      </div>

      <div
        className="mt-2.5 flex gap-[3px]"
        role="img"
        aria-label={`${meter.label}: ${meter.display}`}
      >
        {Array.from({ length: total }, (_, index) => {
          const isFilled = index < filled;
          return reduceMotion ? (
            <span
              key={index}
              className={`h-1 flex-1 rounded-full ${
                isFilled ? "bg-accent" : "bg-border"
              }`}
            />
          ) : (
            <motion.span
              key={index}
              className={`js-reveal h-1 flex-1 rounded-full ${
                isFilled ? "bg-accent" : "bg-border"
              }`}
              initial={{ opacity: 0, scaleY: 0.4 }}
              whileInView={{ opacity: 1, scaleY: 1 }}
              viewport={VIEWPORT}
              transition={{
                duration: DURATION.micro,
                delay: delay + index * 0.018,
                ease: EASE,
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
