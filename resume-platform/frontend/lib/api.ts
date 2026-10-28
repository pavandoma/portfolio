// Small fetch wrapper around the backend API (proxied through /api by the Next.js server).

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ");
    } catch {
      /* keep default message */
    }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => fetch(`/api${path}`, { cache: "no-store" }).then((r) => parse<T>(r)),
  post: <T>(path: string, body?: unknown) =>
    fetch(`/api${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body ?? {}) }).then((r) => parse<T>(r)),
  put: <T>(path: string, body: unknown) =>
    fetch(`/api${path}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => parse<T>(r)),
  patch: <T>(path: string, body: unknown) =>
    fetch(`/api${path}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then((r) => parse<T>(r)),
  del: <T>(path: string) => fetch(`/api${path}`, { method: "DELETE" }).then((r) => parse<T>(r)),
  upload: <T>(path: string, file: File, fields: Record<string, string> = {}) => {
    const form = new FormData();
    form.append("file", file);
    for (const [k, v] of Object.entries(fields)) if (v) form.append(k, v);
    return fetch(`/api${path}`, { method: "POST", body: form }).then((r) => parse<T>(r));
  },
};

/** Poll a background task until it finishes. */
export async function waitForTask<T>(taskId: string, onTick?: (status: string) => void, timeoutMs = 180_000): Promise<T> {
  const started = Date.now();
  for (;;) {
    const t = await api.get<{ status: string; result: T; error: string | null }>(`/tasks/${taskId}`);
    onTick?.(t.status);
    if (t.status === "done") return t.result;
    if (t.status === "failed") throw new ApiError(t.error || "Task failed", 500);
    if (Date.now() - started > timeoutMs) throw new ApiError("Timed out waiting for the task", 504);
    await new Promise((r) => setTimeout(r, 800));
  }
}
