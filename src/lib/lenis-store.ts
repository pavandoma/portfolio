/**
 * Tiny external store for the live Lenis instance.
 *
 * Lenis is created in an effect and consumed by components that mount
 * earlier in the tree (children's effects run before the parent's). Holding
 * it in React state would mean calling setState inside that effect; holding
 * it here lets consumers subscribe through `useSyncExternalStore` instead,
 * which is the pattern React prescribes for exactly this shape of problem.
 */
import type Lenis from "lenis";

let instance: Lenis | null = null;
const listeners = new Set<() => void>();

export function setLenisInstance(next: Lenis | null) {
  instance = next;
  listeners.forEach((listener) => listener());
}

export function getLenisInstance() {
  return instance;
}

export function subscribeLenis(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Server snapshot: there is never a Lenis instance during SSR. */
export function getServerLenisInstance() {
  return null;
}
