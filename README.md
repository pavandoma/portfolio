# voiyu.com

Pavan Srinivas Doma's portfolio: a static Next.js export served from Hostinger.

- `npm run dev` runs it locally on http://localhost:3000.
- `npm run build` writes the whole site to `out/`.

## Layout

- `src/app/page.tsx` is the home page; `src/app/blog/[slug]/` the stories;
  `src/app/home/` repeats the home page for visitors whose browsers remember
  the old WordPress redirect to `/home/`.
- `src/components/site/` holds the page pieces; `src/content/` holds the text
  (`profile.ts`, `site.ts`, `blog.ts`).
- `public/api/mcp.php` is the "add me to your agent" MCP server, served at
  `/mcp`; its data, `/api/agent-profile.json`, is generated from `src/content/`
  at build time.

## Deploying

Upload the contents of `out/` (including the hidden `.htaccess`) into
voiyu.com's `public_html`, leaving `public_html/.private/` (Hostinger's own
config) in place, then clear the site's cache in hPanel; otherwise the server
can keep serving old pages for hours. Don't use an archive deploy that wipes
the folder.
