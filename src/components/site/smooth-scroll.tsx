"use client";

import Lenis from "lenis";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";
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
 * Lenis smooth scroll. It scrolls the real window (no transform hijack) and
 * runs on its own requestAnimationFrame loop (`autoRaf`).
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
      autoRaf: true,
    });
    setLenisInstance(instance);

    if (process.env.NODE_ENV !== "production") {
      // Exposed so scroll behaviour can be inspected from the console.
      Object.assign(window, { __lenis: instance });
    }

    return () => {
      setLenisInstance(null);
      instance.destroy();
    };
  }, []);

  return <>{children}</>;
}
