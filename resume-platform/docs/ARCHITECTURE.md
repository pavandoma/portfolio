# Architecture

## Components

```
 Browser ──► Next.js (frontend/, port 3000)
               │  pages: dashboard, master profile, new job, jobs & matches, resume editor,
               │         resumes & exports, application tracker
               │  /api/[...path] route handler: server-side proxy, adds RIP_API_TOKEN
               ▼
 FastAPI (backend/, port 8000) ──► SQLite (data/resume_platform.db) or PostgreSQL
               │                   files: data/uploads, data/outputs
               ├─► Firecrawl / built-in fetcher (job URLs)      [optional, public URLs only]
               ├─► GitHub REST API (repository evidence)       [optional]
               ├─► LLM provider: Anthropic / OpenAI / Ollama   [optional, off by default]
               └─► MCP validators (stdio or HTTP)              [optional, off by default]

 Claude Code / Codex ──stdio──► app.mcp_server (same database, same services)
```

The backend works fully offline. Every external service is optional, and none of them receives profile
or resume text unless `RIP_ALLOW_EXTERNAL_DATA_SHARING=true`.

## Pipeline

| Step | Module | Output |
|---|---|---|
| Extract text and layout | `app/ingest/extract.py` (PyMuPDF, python-docx) | lines with font size, boldness, position |
| Parse sections and entries | `app/ingest/resume_parser.py` | `ParsedResume` |
| Build the evidence profile | `app/ingest/profile_builder.py`, `claims.py` | `CandidateProfile` + review issues |
| Analyse a posting | `app/jobs/jd_parser.py`, `app/ingest/url_fetch.py` | `JobAnalysis` |
| Match | `app/matching/engine.py` | `MatchReport` (Job Fit, gates, per-requirement evidence) |
| Tailor | `app/tailoring/tailor.py`, `rewrite.py`, `style.py` | `TailoredResume` + change log + reserves |
| Render and fit to the page | `app/render/pdf_writer.py`, `docx_writer.py`, `fit.py` | PDF, DOCX |
| Validate | `app/validation/ats.py`, `integrity.py`, `qa.py`, `adapters/` | `ValidationBundle` |
| Revise (max 3 cycles) | `app/optimize/loop.py` | best iteration + stop reason |
| Persist, version, export | `app/services/*.py`, `app/render/reports.py` | rows, files, ZIP |

### Evidence model

`CandidateProfile` (`app/schemas/profile.py`) holds roles, projects, education, certifications, skills,
evidence items and review issues. Every achievement keeps:

- `original_text`, exactly as imported (never overwritten), and `text`, the current wording;
- `verification`: `unverified`, `verified`, `user_corrected`, `needs_review` or `rejected`;
- `allowed_usage` (`do_not_use` hides it from every resume);
- `metrics`, extracted numbers with their unit and verification state;
- `flags` such as an academic project claiming production use, absolute claims, unclear causality;
- `variants`, alternative phrasings with origin (`rule_cleanup`, `assistant`, `llm`, `user`), a stored
  fact check, and an approval flag.

IDs are stable hashes (`stable_id`) of the source text, so re-importing the same resume keeps your
decisions.

### Truthfulness guarantees

1. **Selection, not invention.** The tailor only chooses, orders and words items that exist in the
   profile. Employers, titles, dates and degrees are copied as they are.
2. **Fact check on every rewording** (`app/tailoring/rewrite.py: fact_check`). A variant fails if it adds a
   number, technology, proper name, year, or a production, leadership or collaboration claim that the
   source does not contain. Failed variants are stored for review but can never be approved or used.
3. **Integrity trace** (`app/validation/integrity.py`). Every bullet, summary sentence and skill on the
   generated resume is traced to profile items. Unsupported claims make the version unapprovable.
4. **Academic context.** Bullets from academic projects never claim production or enterprise use; the
   revision loop rewrites or drops them when they do.
5. **Gaps stay visible.** Missing requirements are listed in the match report and the missing-skills
   report. They are never added to the resume.

### Determinism

Matching and tailoring are deterministic: no randomness and no model calls. Each match report carries an
`input_hash` (SHA-256 over the profile content, the analysed posting, the weights and
`SCORING_VERSION`), so identical inputs are recognisable and always give the same scores. LLM output is only ever a suggested wording variant, and it passes through
the same fact check and approval as any other variant.

### Page fitting

`app/render/fit.py` renders, measures and adjusts until the resume fits its page target (one page for
early-career profiles, two otherwise):

1. tighten type and margins in small steps (10.5 → 10 pt, 0.55 in margins), never below 9.5 pt / 0.5 in;
2. drop the least relevant bullets and projects, recording each one as omitted with its reason;
3. use leftover space for content held in reserve, most relevant first, until the last page is about
   85% full.

Fonts follow the source resume: a Times-like serif (Liberation Serif) when the original used Times, a
Calibri-like sans (Carlito) otherwise, embedded in the PDF.

## Data model (`app/models.py`, migration `alembic/versions/0001_initial_schema.py`)

| Table | Purpose |
|---|---|
| `source_documents` | uploaded files (path, hash, kind, page count) |
| `profiles`, `profile_revisions` | one profile; every change is a new immutable revision (JSON snapshot + reason) |
| `audit_events` | who changed what and when (entity, action, before/after summary) |
| `jobs` | posting text, URL (canonical), dedupe key, analysis JSON |
| `match_reports` | every match run with its weights, input hash and report |
| `resume_versions`, `resume_revisions` | generated versions with content, scores, validation and change log |
| `generated_files` | PDF, DOCX, JSON and Markdown reports for each version |
| `applications` | one per job: status, submitted version, dates, notes |

SQLite is the default. PostgreSQL is used by Docker Compose; the same Alembic migration serves both and
`alembic check` confirms it matches the ORM models.

## Security design

| Concern | Control | Code |
|---|---|---|
| Malicious uploads | magic-byte type check, size limit, PDF page limit, DOCX entry-count and expanded-size limits (zip bombs) | `app/core/security.py: validate_upload` |
| SSRF via job URLs | DNS resolution, public IPs only, manual redirects re-checked on every hop, size and time caps | `assert_public_url`, `app/ingest/url_fetch.py` |
| Prompt injection in postings | injection lines detected and stripped from model input; posting text wrapped as untrusted data | `detect_injection`, `strip_injection`, `wrap_untrusted` |
| Secret leakage | `SecretStr` settings; a logging filter that redacts configured secrets and API-key / bearer-token patterns | `RedactingFilter`, `redact` |
| Unauthorised access | optional bearer token (constant-time compare), CORS restricted to the frontend origin | `app/main.py` |
| External data sharing | remote LLMs and external validators refuse to run without the explicit sharing flag | `app/llm/factory.py`, `app/validation/adapters/mcp_adapter.py` |
| Data deletion | purge endpoint removes all rows and files, then vacuums SQLite | `app/api/routes_system.py: purge` |
| Committed personal data | `data/` is git-ignored; committed examples are contact-masked | `.gitignore`, `mask_contact` |
