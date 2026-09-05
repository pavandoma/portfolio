/**
 * Theme as a tiny external store.
 *
 * The truth lives on `<html data-theme>`: an inline script in the root layout
 * stamps it from localStorage before first paint, so there is no flash. This
 * module mirrors that attribute for React (via `useSyncExternalStore`) and for
 * non-React subscribers such as the canvas renderer, which needs to redraw
 * when the palette changes.
 */

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "theme";

function readDocumentTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

let current: Theme = readDocumentTheme();
const listeners = new Set<() => void>();

export function getTheme(): Theme {
  return current;
}

/** The server always renders dark; the design is dark-first. */
export function getServerTheme(): Theme {
  return "dark";
}

export function subscribeTheme(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setTheme(next: Theme) {
  if (next === current) return;
  current = next;
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, next);
  } catch {
    // Private mode or blocked storage: the choice simply won't persist.
  }
  listeners.forEach((listener) => listener());
}
