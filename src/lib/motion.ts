/**
 * Shared motion tokens.
 *
 * Durations are graded by purpose rather than reused as one global value —
 * feedback must feel instant, entrances can afford to breathe. Easing is
 * deceleration (ease-out) for anything arriving on screen.
 */

export const DURATION = {
  /** Colour/border feedback on hover and focus. */
  feedback: 0.15,
  /** Micro-interactions: lifts, icon nudges. */
  micro: 0.25,
  /** Scroll reveals. */
  reveal: 0.45,
  /** Display type and masked headlines. */
  display: 0.7,
} as const;

export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/**
 * Pointer tilt. Underdamped just enough to feel physical, but settling fast —
 * a card that keeps wobbling after the pointer stops reads as noise.
 */
export const TILT_SPRING = {
  stiffness: 170,
  damping: 20,
  mass: 0.4,
} as const;

export const VIEWPORT = {
  once: true,
  amount: 0.15,
  margin: "0px 0px -80px 0px",
} as const;

/** Max card rotation, degrees. Deliberately small — this is an editorial site. */
export const MAX_TILT_DEG = 5;
