"use client";

import { useRef } from "react";
import { cinematic } from "@/content/cinematic";
import { skills } from "@/content/profile";
import { gsap, useGSAP } from "@/lib/gsap";

/** Skills as a specification sheet: one hairline row per category. */
export function Specs() {
  const sectionRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-row]", {
          opacity: 0,
          y: 18,
          stagger: 0.07,
          duration: 0.6,
          ease: "power2.out",
          scrollTrigger: { trigger: sectionRef.current, start: "top 75%" },
        });
      });
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      id="specs"
      className="bg-background px-6 py-28 sm:px-10 sm:py-40"
      aria-labelledby="specs-title"
    >
      <p className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
        {cinematic.specs.label}
      </p>
      <h2
        id="specs-title"
        className="mt-5 font-sans text-[clamp(2rem,5vw,4.5rem)] leading-[1.02] font-light tracking-[-0.03em] text-foreground"
      >
        {cinematic.specs.title}
      </h2>

      <dl className="mt-20 border-t border-hairline">
        {skills.map((group) => (
          <div
            key={group.category}
            data-row
            className="grid grid-cols-1 gap-3 border-b border-hairline py-7 md:grid-cols-[16rem_1fr] md:gap-10"
          >
            <dt className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted">
              {group.category}
            </dt>
            <dd className="font-sans text-lg leading-relaxed text-foreground/85">
              {group.items.join("  ·  ")}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
