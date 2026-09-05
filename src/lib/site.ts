/**
 * Canonical origin for absolute URLs in metadata, the sitemap, robots, and
 * structured data.
 *
 * Set NEXT_PUBLIC_SITE_URL at build time (see .env.example). The fallback is
 * where the portfolio is meant to live — a subdomain of voiyu.com, kept
 * separate from the WordPress site already installed at the domain root.
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://myportfolio.voiyu.com"
).replace(/\/+$/, "");
