#!/usr/bin/env node
/**
 * Create the login for the learning log's manage page.
 *
 *   node scripts/make-htpasswd.mjs
 *
 * Prompts for a username and password (the password is not echoed) and writes
 * `.htpasswd` — a salted hash, not the password — into ./portfolio-data/
 * (git-ignored). Upload it next to auth.php in the server's portfolio-data/
 * folder. The folder's .htaccess then asks for this login before it serves
 * /learning/manage/ or accepts a save.
 */

import { createHash, randomBytes } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const MIN_LENGTH = 12;
const ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
const md5 = (...parts) => createHash("md5").update(Buffer.concat(parts)).digest();

/** Apache's "$apr1$" MD5-crypt, which every Apache and LiteSpeed accepts. */
export function apr1(password, salt) {
  const pw = Buffer.from(password);
  const sl = Buffer.from(salt);
  const magic = Buffer.from("$apr1$");
  let final = md5(pw, sl, pw);
  const ctx = [pw, magic, sl];
  for (let n = pw.length; n > 0; n -= 16) ctx.push(final.subarray(0, Math.min(16, n)));
  for (let i = pw.length; i; i >>= 1) ctx.push(i & 1 ? Buffer.from([0]) : pw.subarray(0, 1));
  final = md5(...ctx);
  for (let i = 0; i < 1000; i++) {
    const round = [i & 1 ? pw : final];
    if (i % 3) round.push(sl);
    if (i % 7) round.push(pw);
    round.push(i & 1 ? final : pw);
    final = md5(...round);
  }
  const to64 = (v, n) => {
    let out = "";
    for (let i = 0; i < n; i++, v >>= 6) out += ITOA64[v & 0x3f];
    return out;
  };
  const f = final;
  return (
    "$apr1$" + salt + "$" +
    to64((f[0] << 16) | (f[6] << 8) | f[12], 4) +
    to64((f[1] << 16) | (f[7] << 8) | f[13], 4) +
    to64((f[2] << 16) | (f[8] << 8) | f[14], 4) +
    to64((f[3] << 16) | (f[9] << 8) | f[15], 4) +
    to64((f[4] << 16) | (f[10] << 8) | f[5], 4) +
    to64(f[11], 2)
  );
}

function readHidden(prompt) {
  return new Promise((resolve) => {
    process.stdout.write(prompt);
    const stdin = process.stdin;
    let value = "";
    if (stdin.isTTY) stdin.setRawMode(true);
    stdin.resume();
    stdin.setEncoding("utf8");
    const onData = (chunk) => {
      for (const ch of chunk) {
        if (ch === "\r" || ch === "\n" || ch === "\u0004") {
          if (stdin.isTTY) stdin.setRawMode(false);
          stdin.pause();
          stdin.off("data", onData);
          process.stdout.write("\n");
          resolve(value);
          return;
        }
        if (ch === "\u0003") process.exit(130);
        if (ch === "\u007f" || ch === "\b") value = value.slice(0, -1);
        else value += ch;
      }
    };
    stdin.on("data", onData);
  });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const user = await new Promise((resolve) => rl.question("Username: ", resolve));
  rl.close();
  if (!/^[A-Za-z0-9._-]{3,32}$/.test(user)) {
    console.error("Use 3-32 letters, digits, dot, dash or underscore for the username.");
    process.exit(1);
  }
  const first = await readHidden(`Password (at least ${MIN_LENGTH} characters): `);
  if (first.length < MIN_LENGTH) {
    console.error(`Too short: use at least ${MIN_LENGTH} characters.`);
    process.exit(1);
  }
  if (first !== (await readHidden("Again: "))) {
    console.error("Those did not match. Nothing was written.");
    process.exit(1);
  }
  const salt = Array.from(randomBytes(8), (b) => ITOA64[b & 0x3f]).join("");
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  mkdirSync(join(root, "portfolio-data"), { recursive: true });
  const file = join(root, "portfolio-data", ".htpasswd");
  writeFileSync(file, `${user}:${apr1(first, salt)}\n`, { mode: 0o600 });
  console.log(`Wrote ${file}`);
  console.log("Upload it to the server's portfolio-data/ folder, next to auth.php.");
}
