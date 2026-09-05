"use client";

import { useSyncExternalStore } from "react";
import {
  getServerTheme,
  getTheme,
  setTheme,
  subscribeTheme,
} from "@/lib/theme-store";

/**
 * Dark / light switch. Labelled with the mode it will switch *to*, in the
 * same tracked mono as the rest of the nav, with a half-filled disc as the
 * glyph — no sun, no moon.
 */
export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getServerTheme);
  const next = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-pressed={theme === "light"}
      aria-label={`Switch to ${next} mode`}
      className="pointer-events-auto inline-flex items-center gap-2 py-3 font-mono text-[11px] tracking-[0.18em] uppercase text-muted transition-colors duration-150 hover:text-foreground"
    >
      <svg
        viewBox="0 0 16 16"
        aria-hidden="true"
        className="size-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.2"
      >
        <circle cx="8" cy="8" r="6.4" />
        <path d="M8 1.6v12.8A6.4 6.4 0 0 0 8 1.6Z" fill="currentColor" stroke="none" />
      </svg>
      <span>{next}</span>
    </button>
  );
}
