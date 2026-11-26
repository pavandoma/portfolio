"use client";

import { useEffect, useRef } from "react";

/**
 * Two eyes whose pupils track the pointer.
 *
 * Every frame each pupil eases toward a target offset computed from the
 * pointer's angle and distance to that eye's own centre, so the two eyes
 * converge on near points and look parallel at far ones. Nothing re-renders:
 * positions are written straight to `transform`.
 *
 * With no pointer (touch, or the cursor left the window) the eyes drift back
 * to centre. Under reduced motion they still look at the pointer, but snap
 * instead of easing and never blink.
 */
export function EyeCard() {
  const cardRef = useRef<HTMLDivElement>(null);
  const eyes = useRef<(HTMLDivElement | null)[]>([]);
  const pupils = useRef<(HTMLDivElement | null)[]>([]);
  const lids = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pointer = { x: 0, y: 0, active: false };
    const current = [
      { x: 0, y: 0 },
      { x: 0, y: 0 },
    ];
    let raf = 0;
    let last = performance.now();

    const onMove = (e: PointerEvent) => {
      pointer.x = e.clientX;
      pointer.y = e.clientY;
      pointer.active = true;
    };
    const onLeave = () => {
      pointer.active = false;
    };

    const frame = (now: number) => {
      // Time-based easing, so the eyes move at the same speed on 60 Hz and
      // 120 Hz screens. TAU ≈ 0.11 s matches the old 0.14-per-frame at 60 Hz.
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      const ease = reduce ? 1 : 1 - Math.exp(-dt / 0.11);
      eyes.current.forEach((eye, i) => {
        const pupil = pupils.current[i];
        if (!eye || !pupil) return;
        const r = eye.getBoundingClientRect();
        const cx = r.left + r.width / 2;
        const cy = r.top + r.height / 2;
        // Pupil may travel this far from centre before touching the rim.
        const max = r.width * 0.26;

        let tx = 0;
        let ty = 0;
        if (pointer.active) {
          const dx = pointer.x - cx;
          const dy = pointer.y - cy;
          const dist = Math.hypot(dx, dy) || 1;
          // Close pointers move the pupil less, so it never jumps through
          // the centre when the cursor passes over the eye.
          const reach = Math.min(dist / (r.width * 1.5), 1) * max;
          tx = (dx / dist) * reach;
          ty = (dy / dist) * reach;
        }

        const c = current[i];
        c.x += (tx - c.x) * ease;
        c.y += (ty - c.y) * ease;
        pupil.style.transform = `translate(${c.x.toFixed(2)}px, ${c.y.toFixed(2)}px)`;
      });
      raf = requestAnimationFrame(frame);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    raf = requestAnimationFrame(frame);

    // Blink every few seconds, at a slightly irregular interval.
    let blinkTimer: ReturnType<typeof setTimeout> | undefined;
    const blink = () => {
      lids.current.forEach((lid) => {
        lid?.animate(
          [
            { transform: "scaleY(0)" },
            { transform: "scaleY(1)", offset: 0.5 },
            { transform: "scaleY(0)" },
          ],
          { duration: 220, easing: "ease-in-out" },
        );
      });
      blinkTimer = setTimeout(blink, 2600 + Math.random() * 3200);
    };
    if (!reduce) blinkTimer = setTimeout(blink, 1800);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(blinkTimer);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return (
    <div
      ref={cardRef}
      className="relative mx-auto w-full max-w-[22rem] overflow-hidden rounded-[2rem] border border-emerald-400/30 bg-gray-900"
      aria-hidden="true"
    >
      <div>
        {/* Face */}
        <div className="relative flex aspect-[5/4] items-center justify-center gap-[6%] px-[10%]">
          {[0, 1].map((i) => (
            <div
              key={i}
              ref={(el) => {
                eyes.current[i] = el;
              }}
              className="relative aspect-square w-[42%] overflow-hidden rounded-full bg-slate-100"
            >
              <div
                ref={(el) => {
                  pupils.current[i] = el;
                }}
                className="absolute inset-0 flex items-center justify-center will-change-transform"
              >
                <div className="flex aspect-square w-[46%] items-center justify-center rounded-full bg-emerald-500">
                  <div className="relative aspect-square w-[62%] rounded-full bg-gray-950">
                    <div className="absolute left-[22%] top-[18%] aspect-square w-[28%] rounded-full bg-white/90" />
                  </div>
                </div>
              </div>
              {/* Eyelid: scales down from the top on blink. */}
              <div
                ref={(el) => {
                  lids.current[i] = el;
                }}
                className="absolute inset-0 origin-top scale-y-0 bg-gray-700"
              />
            </div>
          ))}
        </div>

        {/* Caption strip */}
        <div className="flex items-center justify-between border-t border-white/5 px-6 py-5">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-gray-400">
              Status
            </p>
            <p className="mt-1 text-sm text-gray-200">Watching for good problems</p>
          </div>
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60 motion-reduce:animate-none" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
        </div>
      </div>
    </div>
  );
}
