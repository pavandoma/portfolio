"use client";

import { useRef } from "react";
import { cinematic } from "@/content/cinematic";
import { certifications, education, experience } from "@/content/profile";
import { gsap, useGSAP } from "@/lib/gsap";

/** Provenance: where the work was done, and what it was trained on. */
export function Timeline() {
  const sectionRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-block]", {
          opacity: 0,
          y: 24,
          stagger: 0.12,
          duration: 0.7,
          ease: "power2.out",
          scrollTrigger: { trigger: sectionRef.current, start: "top 70%" },
        });
      });
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      id="timeline"
      className="bg-background px-6 py-28 sm:px-10 sm:py-40"
      aria-labelledby="timeline-title"
    >
      <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
        {cinematic.timeline.label}
      </p>
      <h2
        id="timeline-title"
        className="mt-5 font-sans text-[clamp(2rem,5vw,4.5rem)] leading-[1.02] font-light tracking-[-0.03em] text-foreground"
      >
        {cinematic.timeline.title}
      </h2>

      <div className="mt-20 grid grid-cols-1 gap-16 lg:grid-cols-[1.3fr_1fr] lg:gap-24">
        <div data-block>
          {experience.map((role) => (
            <article key={role.company}>
              <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
                {role.period} — {role.location}
              </p>
              <h3 className="mt-4 font-sans text-2xl leading-tight font-light tracking-[-0.02em] text-foreground sm:text-3xl">
                {role.role}
              </h3>
              <p className="mt-1.5 text-foreground/60">{role.company}</p>
              <ul className="mt-8 space-y-4 border-t border-hairline pt-8">
                {role.bullets.map((bullet) => (
                  <li
                    key={bullet}
                    className="max-w-2xl leading-relaxed text-pretty text-foreground/70"
                  >
                    {bullet}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <div className="space-y-14">
          <div data-block>
            <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
              Education
            </p>
            <ul className="mt-6 space-y-6">
              {education.map((entry) => (
                <li key={entry.institution} className="border-t border-hairline pt-5">
                  <p className="font-sans text-lg text-foreground">{entry.degree}</p>
                  <p className="mt-1 text-sm text-foreground/60">{entry.institution}</p>
                  <p className="mt-1.5 font-mono text-[11px] tracking-[0.18em] uppercase text-muted">
                    {entry.location} · {entry.period}
                  </p>
                </li>
              ))}
            </ul>
          </div>

          <div data-block>
            <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
              Certification
            </p>
            <ul className="mt-6 space-y-6">
              {certifications.map((cert) => (
                <li key={cert.title} className="border-t border-hairline pt-5">
                  <p className="font-sans text-lg text-foreground">{cert.title}</p>
                  <p className="mt-1 text-sm text-foreground/60">{cert.detail}</p>
                  <p className="mt-1.5 font-mono text-[11px] tracking-[0.18em] uppercase text-muted">
                    {cert.date}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
