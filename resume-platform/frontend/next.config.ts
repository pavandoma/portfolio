import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const here = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image; Vercel (VERCEL=1 at build time) packages the app itself.
  output: process.env.VERCEL ? undefined : "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // This app lives inside a larger repository; resolve modules from this folder only.
  turbopack: { root: here },
  outputFileTracingRoot: here,
};

export default nextConfig;
