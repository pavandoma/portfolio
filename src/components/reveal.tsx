"use client";

import { motion, useInView, useReducedMotion } from "motion/react";
import { useRef, type ReactNode } from "react";

import { DURATION, EASE_OUT as EASE, VIEWPORT } from "@/lib/motion";

/**
 * Scroll-triggered fade-and-rise. Standard tier: 450ms, stagger 0.06s.
 * Under `prefers-reduced-motion` the final state renders immediately.
 */
export function Reveal({
  children,
  delay = 0,
  className,
  as = "div",
  onMount = false,
}: {
  children: ReactNode;
  /** Seconds. For grids, pass `index * 0.06`. */
  delay?: number;
  className?: string;
  as?: "div" | "li" | "section";
  /**
   * Animate on mount rather than on scroll. Use for anything above the fold —
   * `whileInView` waits on IntersectionObserver, which leaves already-visible
   * content blank until it fires.
   */
  onMount?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const Component = motion[as];

  if (reduceMotion) {
    const Static = as;
    return <Static className={className}>{children}</Static>;
  }

  const trigger = onMount
    ? { animate: { opacity: 1, y: 0 } }
    : { whileInView: { opacity: 1, y: 0 }, viewport: VIEWPORT };

  return (
    <Component
      // `js-reveal` lets the no-JS guard in the root layout force the final
      // state — without it these elements would render at opacity 0 forever.
      className={className ? `js-reveal ${className}` : "js-reveal"}
      initial={{ opacity: 0, y: 16 }}
      {...trigger}
      transition={{ duration: DURATION.reveal, delay, ease: EASE }}
    >
      {children}
    </Component>
  );
}

/**
 * Display headline that rises line by line from behind a mask.
 *
 * Each line is a separate element, so the text stays selectable and is read
 * normally by screen readers — no per-character splitting.
 */
/**
 * One masked line.
 *
 * The observer watches the *mask*, never the sliding text. The text starts
 * translated 110% down, which puts it fully outside the mask's
 * `overflow: hidden` box — and IntersectionObserver accounts for ancestor
 * clipping, so a `whileInView` on the text itself reports "not intersecting"
 * forever and the line never appears. Observing the mask breaks that deadlock.
 */
function MaskedLine({
  line,
  index,
  delay,
  lineClassName,
  onMount,
}: {
  line: string;
  index: number;
  delay: number;
  lineClassName?: string;
  onMount: boolean;
}) {
  const maskRef = useRef<HTMLSpanElement>(null);
  const inView = useInView(maskRef, { once: true, amount: 0.15 });
  const reduceMotion = useReducedMotion();
  const show = onMount || inView;

  return (
    <span ref={maskRef} className="block overflow-hidden">
      {reduceMotion ? (
        <span className={lineClassName}>{line}</span>
      ) : (
        <motion.span
          className={`js-reveal block ${lineClassName ?? ""}`}
          initial={{ y: "110%" }}
          animate={show ? { y: "0%" } : { y: "110%" }}
          transition={{
            duration: DURATION.display,
            delay: delay + index * 0.08,
            ease: EASE,
          }}
        >
          {line}
        </motion.span>
      )}
    </span>
  );
}

export function MaskedLines({
  lines,
  className,
  lineClassName,
  delay = 0,
  onMount = false,
}: {
  lines: string[];
  className?: string;
  lineClassName?: string;
  delay?: number;
  /** Animate on mount rather than on scroll. See `Reveal`. */
  onMount?: boolean;
}) {
  return (
    <span className={className}>
      {lines.map((line, index) => (
        <MaskedLine
          key={line}
          line={line}
          index={index}
          delay={delay}
          lineClassName={lineClassName}
          onMount={onMount}
        />
      ))}
    </span>
  );
}

/** Hairline rule that draws itself in from the left. */
export function DrawnRule({ className }: { className?: string }) {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    return <div className={`h-px bg-rule ${className ?? ""}`} />;
  }

  return (
    <motion.div
      className={`js-reveal h-px origin-left bg-rule ${className ?? ""}`}
      initial={{ scaleX: 0 }}
      whileInView={{ scaleX: 1 }}
      viewport={VIEWPORT}
      transition={{ duration: DURATION.display + 0.1, ease: EASE }}
    />
  );
}
