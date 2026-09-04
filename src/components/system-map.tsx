"use client";

import { motion, useReducedMotion } from "motion/react";
import { Tilt } from "@/components/tilt";
import { DURATION, EASE_OUT } from "@/lib/motion";
import { systemMap } from "@/content/profile";

/**
 * Per-tile lift, in px toward the viewer. Varying the depth is what sells the
 * grid as a stack of planes rather than one rotating rectangle.
 */
const TILE_DEPTH = [10, 26, 42, 18, 50, 30, 34, 22];

/** `transform-style` does not inherit — every level between the tilted card
 *  and a lifted tile has to re-declare it or the tile flattens. */
const PRESERVE_3D = { transformStyle: "preserve-3d" } as const;

export function SystemMap() {
  const reduceMotion = useReducedMotion();

  return (
    <Tilt
      className="rounded-lg border border-border bg-card p-5 sm:p-6"
      maxTilt={7}
    >
      <figure style={PRESERVE_3D}>
        <figcaption className="flex items-center justify-between gap-4">
          <span className="eyebrow text-muted-foreground">System map / 01</span>
          <svg
            viewBox="0 0 16 16"
            aria-hidden="true"
            className="size-4 text-muted-foreground"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          >
            <circle cx="8" cy="8" r="6.4" />
            <path d="M1.6 8h12.8M8 1.6c1.7 1.8 2.6 4 2.6 6.4S9.7 12.6 8 14.4C6.3 12.6 5.4 10.4 5.4 8S6.3 3.4 8 1.6Z" />
          </svg>
        </figcaption>

        <ul className="mt-5 grid grid-cols-3 gap-2.5" style={PRESERVE_3D}>
          {systemMap.tiles.map((tile, index) => {
            const depth = TILE_DEPTH[index] ?? 20;
            const tileStyle = {
              backgroundColor: `var(--swatch-${tile.tone})`,
              // Deeper tiles cast a correspondingly softer, larger shadow.
              boxShadow: `0 ${depth / 3}px ${depth / 1.5}px -${depth / 4}px rgba(0,0,0,0.28)`,
            };
            const shared = "flex h-16 items-end rounded-[3px] p-2 sm:h-20";

            return (
              // The lift lives on the wrapper, not the animated tile. Motion
              // writes the `transform` property wholesale to drive `scale`, so
              // a `translateZ` set alongside it in the same style object is
              // silently overwritten and the grid renders flat.
              <li
                key={tile.label}
                style={{ ...PRESERVE_3D, transform: `translateZ(${depth}px)` }}
              >
                {reduceMotion ? (
                  <div className={shared} style={tileStyle}>
                    <span className="sr-only">{tile.label}</span>
                  </div>
                ) : (
                  <motion.div
                    // Always above the fold, so animate on mount rather than
                    // waiting on IntersectionObserver.
                    className={`js-reveal ${shared}`}
                    style={tileStyle}
                    initial={{ opacity: 0, scale: 0.92 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{
                      duration: DURATION.reveal,
                      delay: index * 0.06,
                      ease: EASE_OUT,
                    }}
                  >
                    <span className="sr-only">{tile.label}</span>
                  </motion.div>
                )}
              </li>
            );
          })}
        </ul>

        <ol className="mt-4 flex flex-wrap gap-x-3 gap-y-1">
          {systemMap.tiles.map((tile) => (
            <li key={tile.label} className="eyebrow text-muted-foreground">
              {tile.label}
            </li>
          ))}
        </ol>

        <p className="mt-4 border-t border-border pt-4 text-sm text-muted-foreground">
          {systemMap.caption}
        </p>
      </figure>
    </Tilt>
  );
}
