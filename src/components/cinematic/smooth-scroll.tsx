"use client";

import Lenis from "lenis";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { gsap, ScrollTrigger } from "@/lib/gsap";
import {
  getLenisInstance,
  getServerLenisInstance,
  setLenisInstance,
  subscribeLenis,
} from "@/lib/lenis-store";

/** The live Lenis instance, or null before mount / under reduced motion. */
export function useLenis() {
  return useSyncExternalStore(
    subscribeLenis,
    getLenisInstance,
    getServerLenisInstance,
  );
}

/**
 * Lenis smooth scroll wired into GSAP's ticker.
 *
 * Lenis scrolls the real window (no transform hijack), so ScrollTrigger works
 * unmodified — it only needs to be told when Lenis moves. Driving Lenis from
 * gsap.ticker keeps both on one clock; `lagSmoothing(0)` stops GSAP from
 * pausing after a dropped frame, which would visibly desync the two.
 *
 * Under `prefers-reduced-motion` the page uses native scrolling: no easing,
 * no inertia, nothing between the wheel and the viewport.
 */
export function SmoothScroll({ children }: { children: ReactNode }) {
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;

    const instance = new Lenis({
      lerp: 0.09,
      wheelMultiplier: 0.9,
      smoothWheel: true,
    });

    instance.on("scroll", ScrollTrigger.update);
    const tick = (time: number) => instance.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    setLenisInstance(instance);

    if (process.env.NODE_ENV !== "production") {
      // Exposed so scroll choreography can be inspected from the console.
      Object.assign(window, {
        __lenis: instance,
        __gsap: gsap,
        __ScrollTrigger: ScrollTrigger,
      });
    }

    return () => {
      setLenisInstance(null);
      gsap.ticker.remove(tick);
      instance.destroy();
    };
  }, []);

  return <>{children}</>;
}
