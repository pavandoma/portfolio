"use client";

import { useRef } from "react";
import {
  FrameSequence,
  type FrameSequenceHandle,
  type FrameSource,
} from "@/components/cinematic/frame-sequence";
import { cinematic } from "@/content/cinematic";
import { gsap, useGSAP } from "@/lib/gsap";
import { renderOrbit } from "@/lib/orbit";

const SOURCE: FrameSource = { kind: "procedural", render: renderOrbit };

/** The name breaks across two lines so the wide opening tracking never wraps. */
const NAME_LINES = cinematic.hero.name.split(" ");

/**
 * Pinned for two viewport heights. Scroll progress does three things at once:
 * turns the orbit, tracks the name in from wide to tight, then lets the type
 * fall away so the object has the last word before the story begins.
 */
export function Hero() {
  const sectionRef = useRef<HTMLElement>(null);
  const frameRef = useRef<FrameSequenceHandle>(null);
  const nameRef = useRef<HTMLHeadingElement>(null);
  const roleRef = useRef<HTMLParagraphElement>(null);
  const cueRef = useRef<HTMLParagraphElement>(null);

  useGSAP(
    () => {
      const media = gsap.matchMedia();

      media.add(
        {
          full: "(prefers-reduced-motion: no-preference)",
          reduce: "(prefers-reduced-motion: reduce)",
          narrow: "(max-width: 640px)",
        },
        (context) => {
          // 0.6em of tracking on an eight-letter line clips at phone widths;
          // open less wide there so no letter ever leaves the viewport.
          const openingTracking = context.conditions?.narrow ? "0.26em" : "0.6em";

          if (context.conditions?.reduce) {
            // Final, readable state. No pin, no scrub.
            frameRef.current?.setProgress(0.35);
            gsap.set(nameRef.current, { opacity: 1, letterSpacing: "0.04em" });
            gsap.set(roleRef.current, { opacity: 1 });
            gsap.set(cueRef.current, { opacity: 0 });
            return;
          }

          frameRef.current?.setProgress(0);

          const timeline = gsap.timeline({
            scrollTrigger: {
              id: "hero",
              trigger: sectionRef.current,
              start: "top top",
              end: "+=200%",
              scrub: 1,
              pin: true,
              anticipatePin: 1,
              onUpdate: (self) => frameRef.current?.setProgress(self.progress),
            },
          });

          timeline
            .fromTo(
              nameRef.current,
              { letterSpacing: openingTracking, opacity: 0 },
              { letterSpacing: "0.04em", opacity: 1, duration: 0.45, ease: "none" },
              0,
            )
            .fromTo(
              roleRef.current,
              { opacity: 0, y: 14 },
              { opacity: 1, y: 0, duration: 0.15, ease: "none" },
              0.42,
            )
            .to(cueRef.current, { opacity: 0, duration: 0.08, ease: "none" }, 0.55)
            .to(
              [nameRef.current, roleRef.current],
              { opacity: 0, scale: 0.96, duration: 0.28, ease: "none" },
              0.72,
            );
        },
      );
    },
    { scope: sectionRef },
  );

  return (
    <section
      ref={sectionRef}
      id="top"
      className="relative h-svh overflow-hidden bg-background"
      aria-label="Introduction"
    >
      <FrameSequence
        ref={frameRef}
        source={SOURCE}
        className="absolute inset-0 h-full w-full"
      />

      <div className="relative flex h-full flex-col items-center justify-center px-6 text-center">
        <h1
          ref={nameRef}
          className="font-sans text-[clamp(2.5rem,9vw,9rem)] leading-[0.95] font-light uppercase whitespace-nowrap text-foreground"
        >
          {NAME_LINES.map((line) => (
            <span key={line} className="block">
              {line}
            </span>
          ))}
        </h1>
        <p
          ref={roleRef}
          className="mt-8 font-mono text-[11px] tracking-[0.28em] uppercase text-muted"
        >
          {cinematic.hero.role}
        </p>
      </div>

      <p
        ref={cueRef}
        className="absolute inset-x-0 bottom-8 text-center font-mono text-[10px] tracking-[0.3em] uppercase text-muted"
      >
        {cinematic.hero.cue}
      </p>
    </section>
  );
}
