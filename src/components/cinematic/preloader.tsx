"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useLenis } from "@/components/cinematic/smooth-scroll";
import { gsap, ScrollTrigger, useGSAP } from "@/lib/gsap";

const REDUCE_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReduceMotion(listener: () => void) {
  const query = window.matchMedia(REDUCE_QUERY);
  query.addEventListener("change", listener);
  return () => query.removeEventListener("change", listener);
}

/**
 * Counter preloader, 00 → 100, then the curtain lifts.
 *
 * Rendered on the server too, so the page never flashes its content before
 * the sequence has run. Scrolling is locked while it runs so the pinned hero
 * can't be scrubbed before it's on screen. When the curtain is gone we refresh
 * ScrollTrigger: its measurements were taken with an overlay in the way.
 *
 * Reduced motion: never shown. No JS: hidden via <noscript> in the layout.
 */
export function Preloader() {
  const lenis = useLenis();
  const overlayRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef<HTMLSpanElement>(null);
  const [done, setDone] = useState(false);

  const reduceMotion = useSyncExternalStore(
    subscribeReduceMotion,
    () => window.matchMedia(REDUCE_QUERY).matches,
    () => false,
  );

  const running = !reduceMotion && !done;

  useEffect(() => {
    if (!running || !lenis) return;
    lenis.stop();
    return () => lenis.start();
  }, [running, lenis]);

  useGSAP(
    () => {
      if (!running) return;
      const counter = { value: 0 };

      gsap
        .timeline({
          onComplete: () => {
            setDone(true);
            ScrollTrigger.refresh();
          },
        })
        .to(counter, {
          value: 100,
          duration: 1.3,
          ease: "power2.inOut",
          onUpdate: () => {
            if (counterRef.current) {
              counterRef.current.textContent = String(
                Math.round(counter.value),
              ).padStart(2, "0");
            }
          },
        })
        .to(
          overlayRef.current,
          { yPercent: -100, duration: 0.9, ease: "power4.inOut" },
          "+=0.15",
        );
    },
    { dependencies: [running] },
  );

  if (!running) return null;

  return (
    <div
      ref={overlayRef}
      data-preloader
      className="fixed inset-0 z-[100] flex items-end justify-end bg-curtain p-8 sm:p-12"
      aria-hidden="true"
    >
      <span
        ref={counterRef}
        className="font-mono text-[28vw] leading-none font-light tracking-[-0.06em] text-curtain-foreground tabular-nums sm:text-[18vw]"
      >
        00
      </span>
    </div>
  );
}
