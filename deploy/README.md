# Moving the site to voiyu.com

The portfolio replaces the WordPress site at the root of voiyu.com. The old
myportfolio.voiyu.com subdomain is removed. Steps, in order:

1. **Back up WordPress** before anything is deleted: in hPanel, Websites →
   voiyu.com → Files → Backups → Generate new backup, then download the files
   and the database.
2. **Build:** `npm run build` writes the complete site to `out/`
   (`NEXT_PUBLIC_SITE_URL` defaults to `https://voiyu.com`).
3. **Remove WordPress:** uninstall the WordPress installation with its files
   and database. Leave `public_html/.private/` alone (Hostinger's own config).
4. **Remove the subdomain:** delete myportfolio.voiyu.com and its folder,
   `public_html/myportfolio/`.
5. **Upload** the contents of `out/` into voiyu.com's `public_html`, including
   the hidden `.htaccess`. Don't use a "deploy archive" that wipes the folder:
   it would also remove `.private/`.
6. **Check:**
   - `https://voiyu.com/` shows the home page; `/blog/<slug>/` loads.
   - The agent endpoint answers:
     `curl -s -X POST https://voiyu.com/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`
   - Purge the LiteSpeed cache if the old WordPress page still shows.
