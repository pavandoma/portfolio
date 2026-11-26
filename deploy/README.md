# Moving the site to voiyu.com

The portfolio replaces the WordPress site at the root of voiyu.com, and
myportfolio.voiyu.com redirects there. Steps, in order:

1. **Back up WordPress** before anything is deleted:
   - the whole `public_html` folder of voiyu.com (theme, uploads, plugins,
     `wp-config.php`), as a zip;
   - the WordPress database, as an SQL export.
   Keep both off the server, or at least outside `public_html`.
2. **Build:** `npm run build` writes the complete site to `out/`
   (`NEXT_PUBLIC_SITE_URL` defaults to `https://voiyu.com`).
3. **Replace:** delete WordPress's files from voiyu.com's `public_html`, then
   upload the contents of `out/` into it, including the hidden `.htaccess`.
   **Don't delete the subdomain's folder** (myportfolio.voiyu.com is served from
   a folder inside `public_html`); step 5 turns it into a redirect.
   Leave `portfolio-data/` (beside `public_html`) alone: it holds the learning
   log's progress and passphrase, and `api/progress.php` finds it from either
   address.
4. **Remove WordPress's database** only after the new site is confirmed live
   and the backup from step 1 is safe.
5. **Redirect the old address:** replace the contents of the
   myportfolio.voiyu.com document root with `deploy/myportfolio-redirect/.htaccess`.
6. **Check:**
   - `https://voiyu.com/` shows the new home page; `/blog/<slug>/`, `/learning/` load.
   - `https://myportfolio.voiyu.com/learning/` lands on `https://voiyu.com/learning/`.
   - The agent endpoint answers:
     `curl -s -X POST https://voiyu.com/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`
   - Purge any LiteSpeed / CDN cache if the old WordPress page still shows.
