import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Static export: `next build` writes a complete site to `out/` that any
   * web server can host, including Hostinger's shared plans. Nothing here
   * needs a Node server at runtime — no API routes, no server actions, no
   * dynamic segments — so nothing is lost.
   */
  output: "export",

  // /learning is written as learning/index.html, which Apache serves for
  // /learning/ with no rewrite rules.
  trailingSlash: true,

  // No `next/image` is used; this keeps the door open without a custom
  // loader, since the default optimiser needs a server.
  images: { unoptimized: true },
};

export default nextConfig;
