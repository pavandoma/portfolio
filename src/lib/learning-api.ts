"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import type { DoneMap } from "@/lib/learning-stats";

/**
 * Where progress lives. In production this is the PHP endpoint that ships in
 * public/api/; during development NEXT_PUBLIC_PROGRESS_API points at
 * scripts/dev-progress-server.mjs.
 */
const API = process.env.NEXT_PUBLIC_PROGRESS_API ?? "/api/progress.php";
const PASS_KEY = "learning:passphrase";

// The passphrase is held for the tab's lifetime only (sessionStorage), never
// written to disk by this page, and sent only with changes.
const passListeners = new Set<() => void>();
function subscribePass(listener: () => void) {
  passListeners.add(listener);
  return () => passListeners.delete(listener);
}
function getPass(): string | null {
  try {
    return sessionStorage.getItem(PASS_KEY);
  } catch {
    return null;
  }
}
function setPass(value: string | null) {
  try {
    if (value) sessionStorage.setItem(PASS_KEY, value);
    else sessionStorage.removeItem(PASS_KEY);
  } catch {
    /* private mode: editing just won't persist across reloads */
  }
  passListeners.forEach((listener) => listener());
}

export type LoadState = "loading" | "ready" | "offline";

export function useProgress() {
  const [done, setDone] = useState<DoneMap>({});
  const [updated, setUpdated] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const passphrase = useSyncExternalStore(subscribePass, getPass, () => null);

  useEffect(() => {
    let cancelled = false;
    fetch(API, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: { done?: DoneMap; updated?: string | null }) => {
        if (cancelled) return;
        setDone(data.done ?? {});
        setUpdated(data.updated ?? null);
        setLoad("ready");
      })
      .catch(() => {
        if (!cancelled) setLoad("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const post = useCallback(async (body: Record<string, unknown>) => {
    const res = await fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    return { status: res.status, data } as { status: number; data: Record<string, unknown> };
  }, []);

  /** Try a passphrase; keep it for this tab if the server accepts it. */
  const unlock = useCallback(
    async (candidate: string) => {
      try {
        const { status } = await post({ passphrase: candidate, check: true });
        if (status === 200) {
          setPass(candidate);
          setMessage(null);
          return true;
        }
        setMessage(status === 429 ? "Too many attempts. Try again later." : status === 503 ? "Editing isn't set up on the server yet." : "That isn't the passphrase.");
      } catch {
        setMessage("Couldn't reach the server.");
      }
      return false;
    },
    [post],
  );

  const lock = useCallback(() => {
    setPass(null);
    setMessage(null);
  }, []);

  /** Tick or untick one step. Optimistic: the page updates at once, and rolls back if the server refuses. */
  const toggle = useCallback(
    async (id: string, next: boolean) => {
      if (!passphrase) return;
      const before = done;
      const today = new Date();
      const day = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      setDone((current) => {
        const copy = { ...current };
        if (next) copy[id] = day;
        else delete copy[id];
        return copy;
      });
      try {
        const { status, data } = await post({ passphrase, id, done: next, date: day });
        if (status === 200 && data.done) {
          setDone(data.done as DoneMap);
          setUpdated((data.updated as string | null) ?? null);
          setMessage(null);
          return;
        }
        setDone(before);
        if (status === 401) {
          setPass(null);
          setMessage("The passphrase was rejected. Unlock again to keep editing.");
        } else {
          setMessage("That change wasn't saved. Try again.");
        }
      } catch {
        setDone(before);
        setMessage("Couldn't reach the server — that change wasn't saved.");
      }
    },
    [done, passphrase, post],
  );

  return { done, updated, load, message, owner: Boolean(passphrase), unlock, lock, toggle };
}
