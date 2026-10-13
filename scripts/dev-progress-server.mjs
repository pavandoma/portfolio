#!/usr/bin/env node
/**
 * Local stand-in for public/api/progress.php, so the learning page can be
 * developed without PHP. Same contract: GET returns the state, POST changes it
 * when the passphrase is right. State lives in memory (or in the file named by
 * PROGRESS_STATE_FILE), and is gone when the process stops.
 *
 *   PORTFOLIO_PASSPHRASE=anything node scripts/dev-progress-server.mjs
 *
 * Not for production — the real endpoint is the PHP file.
 */

import { createServer } from "node:http";
import { existsSync, readFileSync, writeFileSync } from "node:fs";

const PORT = Number(process.env.PORT ?? 8787);
const PASSPHRASE = process.env.PORTFOLIO_PASSPHRASE ?? "dev-passphrase";
const STATE_FILE = process.env.PROGRESS_STATE_FILE;

let state = { done: {}, updated: null };
if (STATE_FILE && existsSync(STATE_FILE)) state = JSON.parse(readFileSync(STATE_FILE, "utf8"));

const send = (res, status, body) => {
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Cache-Control": "no-store",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
  });
  res.end(JSON.stringify(body));
};

createServer((req, res) => {
  if (req.method === "OPTIONS") return send(res, 204, {});
  if (!req.url?.startsWith("/progress")) return send(res, 404, { error: "not_found" });
  if (req.method === "GET") return send(res, 200, state);
  if (req.method !== "POST") return send(res, 405, { error: "method_not_allowed" });

  let raw = "";
  req.on("data", (chunk) => (raw += chunk));
  req.on("end", () => {
    let body;
    try {
      body = JSON.parse(raw);
    } catch {
      return send(res, 400, { error: "invalid_json" });
    }
    if (body.passphrase !== PASSPHRASE) return send(res, 401, { error: "unauthorized" });
    if (body.check === true) return send(res, 200, { ok: true });
    if (typeof body.id !== "string" || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(body.id) || typeof body.done !== "boolean") {
      return send(res, 400, { error: "invalid_request" });
    }
    const today = new Date().toISOString().slice(0, 10);
    const date = typeof body.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(body.date) && body.date <= today ? body.date : today;
    if (body.done) state.done[body.id] = date;
    else delete state.done[body.id];
    state.updated = new Date().toISOString();
    if (STATE_FILE) writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
    send(res, 200, state);
  });
}).listen(PORT, () => console.log(`dev progress API on http://localhost:${PORT}/progress  (passphrase: ${PASSPHRASE})`));
