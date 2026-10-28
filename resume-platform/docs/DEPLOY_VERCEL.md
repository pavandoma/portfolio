# Deploy to Vercel

The platform runs on Vercel as two projects built from this repository:

| Project | Root directory | What it is | Who can reach it |
|---|---|---|---|
| `resume-platform` | `resume-platform/frontend` | the Next.js app you open | only you: Vercel Authentication on all deployments |
| `resume-platform-api` | `resume-platform/backend` | the FastAPI backend | anyone can reach the URL, but every `/api` route except `/api/health` needs the secret token that only the app's server holds |

Data lives in a Postgres database (Neon, added from the Vercel Marketplace). Uploaded resumes and generated
PDF/DOCX files are stored in that database too, because Vercel functions have no permanent disk.

Cost: Vercel's Hobby plan (personal, non-commercial use) and Neon's free plan are enough for one person.

## What changes automatically on Vercel

Vercel sets `VERCEL=1`, and the backend switches to its hosted defaults:

| Setting | Local default | On Vercel |
|---|---|---|
| `RIP_STORAGE` | `fs` (files on disk) | `db` (files in Postgres; `/tmp` is only a cache) |
| `RIP_AUTO_MIGRATE` | off (tables created directly) | on (Alembic migrations at start, with a lock so parallel cold starts are safe) |
| `RIP_DATA_DIR` | `resume-platform/data` | `/tmp/rip-data` |
| `RIP_REQUIRE_TOKEN` | off | on: the API answers 503 until `RIP_API_TOKEN` is set |
| `RIP_EXPOSE_DOCS` | on (`/docs`) | off |

Without `DATABASE_URL`, the backend answers 503 instead of silently keeping data in a temporary file.

## Steps

### 0. Put the code on `main`

Vercel deploys a project's production branch, normally `main`. Merge the branch that contains
`resume-platform/` into `main` first (on GitHub: open a pull request from the branch and merge it).
The portfolio site at the repository root ignores `resume-platform/` (see the root `tsconfig.json` and
`eslint.config.mjs`), so the merge does not affect it.

### 1. Make a secret token

Any long random string. In PowerShell:

```powershell
$b = New-Object byte[] 36; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString("x2") })
```

On Mac or Linux: `openssl rand -hex 36`. Keep it private; you will paste it into both projects.

### 2. Create the backend project

1. Open https://vercel.com/new and import the `portfolio` repository (allow Vercel's GitHub app access to it
   if asked).
2. Project name: `resume-platform-api`.
3. Root Directory: **Edit** → `resume-platform/backend`. The framework is detected as **FastAPI**.
4. Environment Variables: `RIP_API_TOKEN` = your token.
5. **Deploy**. The API answers 503 until the database exists; that is expected.

### 3. Add the database

1. In the `resume-platform-api` project: **Storage** → **Create Database** → **Neon** (Postgres) → the free
   plan. Choose a region close to you (US East matches Vercel's default function region).
2. Connect it to `resume-platform-api` for Production and Preview. This adds `DATABASE_URL`.
3. **Deployments** → the latest deployment → **⋯** → **Redeploy**, so the backend picks up `DATABASE_URL`.
   The first request creates the tables.

Check: `https://<backend domain>/api/health` returns `{"status":"ok",...}`, and
`https://<backend domain>/api/system/status` returns `401` (no token), not `503`.

### 4. Create the app project

1. https://vercel.com/new again, same repository.
2. Project name: `resume-platform`.
3. Root Directory: `resume-platform/frontend`. Framework: **Next.js**.
4. Environment Variables:
   - `BACKEND_URL` = the backend's production address, e.g. `https://resume-platform-api.vercel.app`
     (no trailing slash; use the domain shown on the backend project's page).
   - `BACKEND_API_TOKEN` = the same token.
5. **Deploy**.

### 5. Lock the app to your account

`resume-platform` → **Settings** → **Deployment Protection** → **Vercel Authentication** → **All
Deployments** → **Save**. Visitors now have to sign in with a Vercel account that has access to the project,
which is only you. This is free on every plan.

Leave the backend on the default protection: its production address must stay reachable by the app's
server, and it is already guarded by the token.

### 6. Use it

Open the app's address (shown on the `resume-platform` project page), sign in to Vercel when asked, then
**Master profile** → upload your resume → **Add wording pack**
(`resume-platform/examples/suggestion-packs/pavan-doma.yaml`) → **New job analysis**.

## Updating

Every push to `main` redeploys both projects. Pushes to other branches create protected preview deployments.

## Limits on Vercel

- **Uploads up to 4.5 MB** (Vercel's request size limit). Resumes are far smaller.
- **No `pdftotext` check**: Poppler is not installed on Vercel functions. The PyMuPDF and python-docx
  parse-back checks still run.
- **Fonts**: the Carlito / Liberation fonts are not on Vercel, so PDFs use the standard Times / Helvetica
  faces. They read the same to people and to ATS parsers.
- **Cold starts**: the first request after a quiet period takes a few seconds longer (Vercel function start,
  and Neon waking an idle database).

## Your data

Your profile, jobs, resumes and files live in the Neon database attached to `resume-platform-api`.
**Delete all my data** (Master profile → History & data) deletes every row. Postgres and Neon's
point-in-time restore can keep deleted data for a limited time; to erase everything at once, delete the
database itself in the project's **Storage** tab.
