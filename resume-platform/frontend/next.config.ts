import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const here = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // This app lives inside a larger repository; resolve modules from this folder only.
  turbopack: { root: here },
  outputFileTracingRoot: here,
};

export default nextConfig;
