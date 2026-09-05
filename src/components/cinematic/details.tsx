"use client";

import { useRef } from "react";
import { cinematic, parseFigure } from "@/content/cinematic";
import { projects } from "@/content/profile";
import { gsap, useGSAP } from "@/lib/gsap";

/**
 * Macro details. Each project is one tall frame: its figure counts up under
 * the scrollbar, a hairline draws across, the copy rises in. Not pinned —
 * the two pins are spent on the hero and the story, and the guidance is firm
 * that more than two fights native scroll.
 */
export function Details() {
  const sectionRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const media = gsap.matchMedia();

      media.add("(prefers-reduced-motion: no-preference)", () => {
        const rows = gsap.utils.toArray<HTMLElement>("[data-detail]");

        rows.forEach((row) => {
          const figure = row.querySelector<HTMLElement>("[data-figure]");
          const rule = row.querySelector<HTMLElement>("[data-rule]");
          const copy = row.querySelectorAll<HTMLElement>("[data-copy]");

          const trigger = {
            trigger: row,
            start: "top 80%",
            end: "top 35%",
            scrub: true,
          };

          if (figure) {
            const target = parseFigure(figure.dataset.figure ?? "0");
            const counter = { value: 0 };
            gsap.to(counter, {
              value: target.value,
              ease: "none",
              scrollTrigger: trigger,
              onUpdate: () => {
                figure.textContent = `${counter.value.toFixed(target.decimals)}${target.suffix}`;
              },
            });
          }

          if (rule) {
            gsap.fromTo(
              rule,
              { scaleX: 0 },
              { scaleX: 1, ease: "none", scrollTrigger: trigger },
            );
          }

          gsap.fromTo(
            copy,
            { opacity: 0, y: 24 },
            { opacity: 1, y: 0, stagger: 0.08, ease: "none", scrollTrigger: trigger },
          );
        });
      });
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      id="details"
      className="bg-background px-6 py-28 sm:px-10 sm:py-40"
      aria-labelledby="details-title"
    >
      <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
        {cinematic.details.label}
      </p>
      <h2
        id="details-title"
        className="mt-5 max-w-3xl font-sans text-[clamp(2rem,5vw,4.5rem)] leading-[1.02] font-light tracking-[-0.03em] text-foreground"
      >
        {cinematic.details.title}
      </h2>

      <ol className="mt-24 sm:mt-32">
        {projects.map((project, index) => {
          const figure = parseFigure(project.meter.display);
          return (
            <li
              key={project.slug}
              data-detail
              className="grid min-h-[70vh] grid-cols-1 content-center gap-10 py-16 lg:grid-cols-[1fr_1.2fr] lg:gap-20"
            >
              <div>
                <span className="font-mono text-[11px] tracking-[0.24em] text-muted tabular-nums">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <p
                  data-figure={project.meter.display}
                  className="mt-4 font-sans text-[clamp(4rem,12vw,11rem)] leading-none font-light tracking-[-0.05em] text-lit tabular-nums"
                >
                  {`${(0).toFixed(figure.decimals)}${figure.suffix}`}
                </p>
                <p className="mt-3 font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
                  {project.meter.label}
                </p>
              </div>

              <div className="self-end">
                <div
                  data-rule
                  className="h-px origin-left bg-hairline"
                  aria-hidden="true"
                />
                <p
                  data-copy
                  className="mt-8 font-mono text-[11px] tracking-[0.24em] uppercase text-muted"
                >
                  {project.kicker}
                </p>
                <h3
                  data-copy
                  className="mt-3 font-sans text-2xl leading-tight font-light tracking-[-0.02em] text-balance text-foreground sm:text-3xl"
                >
                  {project.title}
                </h3>
                <p
                  data-copy
                  className="mt-4 max-w-xl leading-relaxed text-pretty text-foreground/70"
                >
                  {project.summary}
                </p>
                <ul
                  data-copy
                  className="mt-8 flex flex-wrap gap-x-5 gap-y-2 font-mono text-[11px] tracking-[0.18em] uppercase text-muted"
                >
                  {project.tech.map((tech) => (
                    <li key={tech}>{tech}</li>
                  ))}
                </ul>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
