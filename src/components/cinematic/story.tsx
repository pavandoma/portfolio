"use client";

import { useRef } from "react";
import { cinematic } from "@/content/cinematic";
import { gsap, useGSAP } from "@/lib/gsap";

/** Where each line's reveal sits on the 0–1 timeline. */
const LINE_FIRST = 0.24;
const LINE_GAP = 0.22;
const LINE_DURATION = 0.16;
const lineStart = (index: number) => LINE_FIRST + index * LINE_GAP;
const lineEnd = (index: number) => lineStart(index) + LINE_DURATION;

/**
 * "Crafted in darkness." Pinned for one and a half viewports; each line is
 * revealed in turn by the scrollbar, and an index in the corner keeps count.
 */
export function Story() {
  const sectionRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const linesRef = useRef<HTMLParagraphElement[]>([]);
  const indexRef = useRef<HTMLSpanElement>(null);

  const total = cinematic.story.lines.length;

  useGSAP(
    () => {
      const media = gsap.matchMedia();

      media.add(
        {
          full: "(prefers-reduced-motion: no-preference)",
          reduce: "(prefers-reduced-motion: reduce)",
        },
        (context) => {
          if (context.conditions?.reduce) {
            if (indexRef.current) {
              indexRef.current.textContent = `${String(total).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;
            }
            return;
          }

          const timeline = gsap.timeline({
            scrollTrigger: {
              id: "story",
              trigger: sectionRef.current,
              start: "top top",
              end: "+=150%",
              scrub: 1,
              pin: true,
              anticipatePin: 1,
            },
            // The counter reads the timeline's own (eased) progress, not the
            // raw scroll position, so it ticks exactly as each line lands.
            onUpdate: () => {
              const progress = timeline.progress();
              const revealed = cinematic.story.lines.filter(
                (_, index) => progress >= lineEnd(index),
              ).length;
              if (indexRef.current) {
                indexRef.current.textContent = `${String(revealed).padStart(2, "0")} / ${String(total).padStart(2, "0")}`;
              }
            },
          });

          timeline.fromTo(
            titleRef.current,
            { opacity: 0, y: 32 },
            { opacity: 1, y: 0, duration: 0.18, ease: "none" },
            0,
          );

          linesRef.current.forEach((line, index) => {
            timeline.fromTo(
              line,
              { opacity: 0, y: 22 },
              { opacity: 1, y: 0, duration: LINE_DURATION, ease: "none" },
              lineStart(index),
            );
          });

          // Pad to exactly 1s so scroll progress maps 1:1 onto the timeline.
          // Without this ScrollTrigger squeezes every reveal into the first
          // 84% of the pin. The remainder is a deliberate hold on the last
          // line before the section releases.
          timeline.to({}, { duration: Math.max(0, 1 - timeline.duration()) });
        },
      );
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      id="story"
      className="relative h-svh overflow-hidden bg-background"
      aria-labelledby="story-title"
    >
      <div className="flex h-full flex-col justify-between px-6 py-24 sm:px-10 sm:py-28">
        <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
          {cinematic.story.label}
        </p>

        <div className="max-w-4xl">
          <h2
            id="story-title"
            ref={titleRef}
            className="font-sans text-[clamp(2.25rem,6.5vw,6rem)] leading-[1] font-light tracking-[-0.03em] text-foreground"
          >
            {cinematic.story.title}
          </h2>

          <div className="mt-12 space-y-5 sm:mt-16">
            {cinematic.story.lines.map((line, index) => (
              <p
                key={line}
                ref={(element) => {
                  if (element) linesRef.current[index] = element;
                }}
                className="max-w-2xl font-sans text-lg leading-relaxed text-pretty text-foreground/85 sm:text-xl"
              >
                {line}
              </p>
            ))}
          </div>
        </div>

        <div className="flex items-end justify-between">
          <span className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
            Origin
          </span>
          <span
            ref={indexRef}
            className="font-mono text-[11px] tracking-[0.24em] text-muted tabular-nums"
          >
            00 / {String(total).padStart(2, "0")}
          </span>
        </div>
      </div>
    </section>
  );
}
