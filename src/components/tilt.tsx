"use client";

import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "motion/react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { MAX_TILT_DEG, TILT_SPRING } from "@/lib/motion";

/**
 * Pointer-driven 3D tilt.
 *
 * Deliberately gated: it runs only for fine pointers (mouse/trackpad) and only
 * when reduced motion is off. Touch users get the flat card — a tilt bound to
 * `pointermove` on touch fires once on tap and then sticks, which is worse than
 * no effect at all.
 *
 * Rotation is driven from the *outer*, un-rotated wrapper. Measuring the inner
 * element would feed its own rotation back into the next frame's calculation
 * and make the card jitter.
 */
export function Tilt({
  children,
  className,
  maxTilt = MAX_TILT_DEG,
  style,
}: {
  children: ReactNode;
  className?: string;
  maxTilt?: number;
  style?: CSSProperties;
}) {
  const reduceMotion = useReducedMotion();
  const [finePointer, setFinePointer] = useState(false);
  const frameRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = window.matchMedia("(pointer: fine)");
    const sync = () => setFinePointer(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  // Normalised pointer position within the card, -0.5 … 0.5 on each axis.
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);

  const rotateX = useSpring(
    useTransform(pointerY, [-0.5, 0.5], [maxTilt, -maxTilt]),
    TILT_SPRING,
  );
  const rotateY = useSpring(
    useTransform(pointerX, [-0.5, 0.5], [-maxTilt, maxTilt]),
    TILT_SPRING,
  );

  const active = finePointer && !reduceMotion;

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const frame = frameRef.current;
      if (!frame) return;
      const rect = frame.getBoundingClientRect();
      pointerX.set((event.clientX - rect.left) / rect.width - 0.5);
      pointerY.set((event.clientY - rect.top) / rect.height - 0.5);
    },
    [pointerX, pointerY],
  );

  const handlePointerLeave = useCallback(() => {
    pointerX.set(0);
    pointerY.set(0);
  }, [pointerX, pointerY]);

  if (!active) {
    return (
      <div className={className} style={style}>
        {children}
      </div>
    );
  }

  return (
    <div
      ref={frameRef}
      style={{ perspective: 900 }}
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
    >
      <motion.div
        className={className}
        style={{ ...style, rotateX, rotateY, transformStyle: "preserve-3d" }}
      >
        {children}
      </motion.div>
    </div>
  );
}

/**
 * Lifts a child toward the viewer inside a `Tilt`, so the card reads as layered
 * rather than as one flat plane rotating. Inert outside a 3D context.
 */
export function TiltLayer({
  children,
  z = 20,
  className,
}: {
  children: ReactNode;
  /** Pixels toward the viewer. */
  z?: number;
  className?: string;
}) {
  return (
    <div className={className} style={{ transform: `translateZ(${z}px)` }}>
      {children}
    </div>
  );
}
