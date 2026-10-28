# Resume Intelligence Platform

A local-first application that tailors a resume to a job posting **without inventing anything**.
You import your master resume once, review and verify what it says, and then for each job it:

1. analyses the posting (requirements, skills ranked by importance, gates such as years, degree, sponsorship);
2. matches the posting against your evidence and explains a transparent **Job Fit** score;
3. builds a tailored one-page resume that follows recruiter-reading research (exact title under the name,
   three-sentence summary, skills in the posting's order, strongest evidence first);
4. renders PDF and DOCX, parses them back like an ATS would, traces every claim to your profile and
   checks style;
5. revises the draft up to three times, then shows you a side-by-side diff for approval;
6. keeps every version, and records which version you sent to which employer.

Priority order everywhere: **truthful qualifications > job fit > readability > ATS parsing > cosmetic score.**
Scores are heuristics computed by this tool. They are never presented as an employer's ATS score.

| Area | Where |
|---|---|
| Backend (FastAPI, SQLAlchemy, ReportLab, PyMuPDF) | [`backend/`](backend) |
| Frontend (Next.js 16, Tailwind 4, shadcn/ui) | [`frontend/`](frontend) |
| Architecture | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| REST API | [`docs/API.md`](docs/API.md) |
| How scores work | [`docs/SCORING.md`](docs/SCORING.md) |
| LLMs, MCP, Firecrawl, GitHub, external validators | [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) |
| Rules taken from the source documents | [`docs/SOURCE_ANALYSIS.md`](docs/SOURCE_ANALYSIS.md) |
| Example outputs (contact details masked) | [`docs/examples/`](docs/examples) |
| Deploying to Vercel | [`docs/DEPLOY_VERCEL.md`](docs/DEPLOY_VERCEL.md) |

## Run it locally (no Docker)

**Windows, one command** (PowerShell, in `resume-platform`): installs everything on the first run, starts
both servers in their own windows and opens the app. Not yet tested on a Windows machine.

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

**Mac / Linux, step by step:**

Requirements: Python 3.11+ (tested with 3.13) and Node.js 20+ (tested with 22). Optional but recommended:
`poppler-utils` (an independent `pdftotext` parse-back check) and the Carlito / Liberation fonts
(`fonts-crosextra-carlito fonts-liberation` on Debian/Ubuntu). Without those fonts, PDFs fall back to the
built-in Helvetica / Times faces.

Backend (terminal 1):

```bash
cd resume-platform/backend
```

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements-dev.txt
```

```bash
.venv/bin/alembic upgrade head
```

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend (terminal 2):

```bash
cd resume-platform/frontend
```

```bash
npm ci
```

```bash
npm run dev
```

Open http://localhost:3000. Data (SQLite database, uploads, generated files) lives in `resume-platform/data/`,
which is git-ignored. Settings come from environment variables or `resume-platform/.env`
(copy [`.env.example`](.env.example)); nothing is required for the core workflow.

Production-style frontend: `npm run build`, then `node .next/standalone/server.js` after copying
`.next/static` into `.next/standalone/.next/` (the Dockerfile does exactly this).

## Run it with Docker Compose

PostgreSQL, backend and frontend, published on 127.0.0.1 only:

```bash
cd resume-platform
```

```bash
cp .env.example .env
```

```bash
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
```

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before it starts. Data is kept in the `pgdata` and
`appdata` volumes; `docker compose down -v` deletes it.

## Run it on Vercel

Two Vercel projects (app and backend) plus a free Neon Postgres database, with the app locked to your
Vercel account. Step-by-step: [`docs/DEPLOY_VERCEL.md`](docs/DEPLOY_VERCEL.md).

## The workflow in the app

| Step | Page |
|---|---|
| 1. Import the master resume (PDF, DOCX or TXT) | **Master profile** |
| 2. Review parsed facts, verify or correct claims, answer open questions, approve wording | **Master profile** |
| 3. Add a job by URL or pasted text (duplicates are detected) | **New job analysis** |
| 4. Read the match report: score breakdown, gates, missing skills, evidence per requirement | **Jobs & matches** → job |
| 5–7. Generate; validation and up to three revision cycles run automatically | **Jobs & matches** → job |
| 8. Review the side-by-side diff, edit bullets, approve | **Resume editor** |
| 9. Download PDF, DOCX, JSON and reports, or one ZIP | **Resume editor** / **Resumes & exports** |
| 10. Record the application and the exact version sent | **Application tracker** |

Twelve reusable variants (AI Engineer, Data Analyst, Data Engineer, ...) can be generated without a posting
from **Resumes & exports**.

## Command line

```bash
cd resume-platform/backend
```

```bash
.venv/bin/python -m app.cli import-resume ../data/inputs/master_resume.pdf
```

```bash
.venv/bin/python -m app.cli analyze-job --file posting.txt
```

```bash
.venv/bin/python -m app.cli generate --job <job_id> --out ../data/out
```

```bash
.venv/bin/python -m app.cli samples --out ../data/samples
```

`samples` runs the four synthetic test postings (AI Engineer, ML Engineer, Data Engineer, Data Analyst)
against the imported profile and writes every output file per posting.

## Use it from Claude Code or Codex (MCP)

The backend ships an MCP server (stdio) with the tools `profile_summary`, `analyze_job`, `match_job`,
`generate_resume`, `list_variants`, `list_applications` and `update_application`. It uses the same local
database as the web app, returns file paths instead of uploading anything, and never submits applications.

Claude Code (`.mcp.json` in your project, or `claude mcp add`):

```json
{
  "mcpServers": {
    "resume-platform": {
      "command": "/absolute/path/to/resume-platform/backend/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "env": { "PYTHONPATH": "/absolute/path/to/resume-platform/backend" }
    }
  }
}
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.resume-platform]
command = "/absolute/path/to/resume-platform/backend/.venv/bin/python"
args = ["-m", "app.mcp_server"]
env = { PYTHONPATH = "/absolute/path/to/resume-platform/backend" }
```

Job-search agents can also post batches of postings to `POST /api/agent/jobs/import` and read the
pipeline from `GET /api/agent/summary`.

## Tests

```bash
cd resume-platform/backend
```

```bash
.venv/bin/python -m pytest -q
```

The suite covers ingestion, job analysis, matching, tailoring rules, rendering, ATS parse-back, integrity,
QA, the revision loop, LLM adapters (against mocked endpoints), the MCP client and server, the REST API,
and end-to-end runs that start the real backend and frontend servers. Tests that need the real master
resume look for `data/inputs/master_resume.pdf` and are skipped without it. To also test PostgreSQL,
point `RIP_TEST_POSTGRES_URL` at a **disposable** database (the test drops its tables when done):

```bash
RIP_TEST_POSTGRES_URL=postgresql+psycopg://user@127.0.0.1:5432/rip_test .venv/bin/python -m pytest -q tests/test_phase5_e2e.py
```

Frontend checks: `npm run lint`, `npm run typecheck` and `npm run build` in `frontend/`.

## Security and privacy

- Everything runs on your machine. Compose publishes ports on 127.0.0.1 only; the database is not published.
- Secrets are read from the environment or `.env` (git-ignored) and are redacted from logs.
- Uploads are checked by content (magic bytes), size, page count and archive structure.
- Job URLs are fetched only from public addresses, re-checked on every redirect, with size and time limits.
- Job text is treated as untrusted data: prompt-injection lines are detected, reported and never followed.
- No profile or resume text leaves the machine unless you set `RIP_ALLOW_EXTERNAL_DATA_SHARING=true` and
  configure a remote model or external validator. Local models (Ollama) and local validators do not need it.
- Optional `RIP_API_TOKEN` protects the API; the Next.js server adds it, so it never reaches the browser.
- **Delete all my data** (Master profile → History & data, or `POST /api/system/purge`) removes every database
  row and file; with SQLite the database file is also vacuumed so deleted text does not linger on disk.
- The platform never submits applications and never fabricates employers, titles, dates, degrees,
  certifications, metrics, tools or responsibilities.

## Known limitations

- Remote LLM providers (Anthropic, OpenAI) and Ollama are tested against mocked HTTP endpoints only; no
  live API call was made while building this. With `LLM_PROVIDER=none` (the default) everything works
  without a model.
- No external ATS or resume-scoring service is connected. The HireLayer MCP server is described in
  `examples/mcp-validators.example.json` (disabled); its tool argument names are not yet verified.
  See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).
- The Docker images were not built in the development environment (its network policy blocks Docker Hub).
  The Compose file is validated, PostgreSQL migrations are tested against PostgreSQL 16, and the standalone
  frontend server was run the way the image runs it.
- Scanned (image-only) PDFs are rejected with an explanation; there is no OCR.
- Matching uses a curated skills taxonomy (about 200 skills, mostly data, ML and software). Postings
  far outside those fields get less precise skill matching.
