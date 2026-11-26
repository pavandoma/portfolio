/**
 * Canonical origin for absolute URLs in metadata, the sitemap, robots, and
 * structured data.
 *
 * Set NEXT_PUBLIC_SITE_URL at build time (see .env.example). The fallback is
 * the main domain, where the site replaced the old WordPress install. The old
 * subdomain, myportfolio.voiyu.com, redirects here (deploy/myportfolio-redirect).
 */
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://voiyu.com"
).replace(/\/+$/, "");
