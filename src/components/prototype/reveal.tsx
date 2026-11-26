"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Fades and lifts its child into place the first time it scrolls into view.
 * Under reduced motion it is shown in place with no transition.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
  from = "up",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  from?: "up" | "right";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const hidden = from === "up" ? "translate-y-6" : "translate-x-4";

  return (
    <div
      ref={ref}
      data-reveal=""
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-[opacity,translate] duration-[600ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:translate-none motion-reduce:opacity-100 motion-reduce:transition-none ${
        shown ? "translate-none opacity-100" : `${hidden} opacity-0`
      } ${className}`}
    >
      {children}
    </div>
  );
}
