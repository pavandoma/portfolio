# REST API

Base URL: `http://127.0.0.1:8000` (the Next.js frontend proxies `/api/*` to it). Interactive OpenAPI docs
are served at `/docs` and the schema at `/openapi.json`.

**Authentication.** None by default (local use). If `RIP_API_TOKEN` is set, every `/api/*` route except
`/api/health` needs `Authorization: Bearer <token>` (or `?token=` for direct file links).

**Errors.** `400` invalid input or a rule violation (the `detail` field explains it), `404` not found,
`422` request validation, `401` missing or wrong token.

## System

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/health` | | `{"status": "ok", "version": "1.0.0"}` |
| GET | `/api/system/status` | | database kind, profile state, LLM provider, validator adapters, pdftotext, Firecrawl, data-sharing and auth flags, counts |
| GET | `/api/variants` | | the 12 reusable resume variants |
| GET | `/api/tasks/{task_id}` | | status of a background task (`queued`, `running`, `done`, `failed`) and its result |
| GET | `/api/audit?limit=` | | audit trail, newest first |
| POST | `/api/system/purge` | `{"confirm": "DELETE ALL MY DATA"}` | deletes every row and file; vacuums SQLite |

## Master profile

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/profile/import` | multipart `file` (PDF, DOCX, TXT) | parses and creates a new revision; decisions on unchanged items carry over |
| GET | `/api/profile` | | current profile, revision and completeness |
| GET | `/api/profile/revisions` | | all revisions (newest first) |
| GET | `/api/profile/revisions/{revision_id}` | | the full profile as it was at that revision |
| PATCH | `/api/profile/items/{item_id}` | `{"patch": {...}}` | edit any role, project, achievement, education, certification or skill (allowed fields depend on the item type, e.g. `verification`, `note`, `text`, `allowed_usage`) |
| PATCH | `/api/profile/personal` | `name`, `email`, `phone`, `location`, `links` | |
| PATCH | `/api/profile/work-authorization` | `status`, `note`, `has_security_clearance` | status: `unknown`, `citizen`, `permanent_resident`, `authorized_no_sponsorship`, `authorized_requires_future_sponsorship`, `requires_sponsorship` |
| POST | `/api/profile/achievements` | `{"parent_id", "text"}` | adds an achievement to a role or project |
| POST | `/api/profile/achievements/{id}/variants` | `{"text", "emphasis": []}` | adds a wording variant; it is fact-checked and starts unapproved |
| POST | `/api/profile/achievements/{id}/variants/{variant_id}/approval` | `{"approved": true}` | approval is refused if the fact check failed |
| POST | `/api/profile/achievements/{id}/suggest` | | asks the configured LLM for fact-checked variants (`400` if no model is configured) |
| POST | `/api/profile/issues/{issue_id}` | `{"status": "resolved", "resolution"}` | status: `open`, `resolved`, `dismissed` |
| POST | `/api/profile/suggestion-pack` | multipart `file` (YAML/JSON) | applies a wording pack (see `examples/suggestion-packs/`) |
| GET | `/api/profile/suggest-pack-template` | | a pack skeleton for your profile |
| POST | `/api/profile/evidence` | `kind`, `title`, `uri`, `description`, `linked_ids` | kind: `document`, `link`, `note`, `certificate` |
| POST | `/api/profile/evidence/github` | `{"url", "project_id"}` | reads a public repository (languages, topics, README) as project evidence |
| POST | `/api/profile/documents` | multipart `file` | another resume version, LinkedIn export or transcript: stored as evidence; differing contact details become review issues |

## Jobs and matching

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/jobs` | `text` or `url`, optional `title`, `company`, `allow_duplicate`, `fetch_with` (`auto`, `builtin`, `firecrawl`) | analyses the posting; returns `duplicate: true` and the existing job when it was seen before |
| POST | `/api/jobs/async` | same | background version; poll `/api/tasks/{id}` |
| POST | `/api/jobs/upload` | multipart `file`, optional `title`, `company`, `url` | posting as PDF, DOCX or TXT |
| GET | `/api/jobs` | | all jobs, newest first (fit scores and statuses are in `/api/applications`) |
| GET / PATCH / DELETE | `/api/jobs/{job_id}` | PATCH: `title`, `company`, `location` | DELETE also removes its matches, resumes and files |
| POST | `/api/jobs/{job_id}/refine` | | optional LLM re-check of requirement categories (only verbatim-anchored answers are accepted) |
| POST | `/api/jobs/{job_id}/match` | optional weights `{"required", "experience", "keywords", "impact", "ats", "clarity"}` | runs a new match |
| GET | `/api/jobs/{job_id}/match` | | latest match (runs one if none exists) |
| GET | `/api/jobs/{job_id}/matches` | | match history |

## Resumes

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/resumes` | `job_id` or `variant`, optional `page_target`, `use_unapproved_wording`, `font_family` (`sans`, `serif`), `max_cycles`, `weights`, `notes` | generate, validate and revise; returns the version with scores, files and change log |
| POST | `/api/resumes/async` | same | background version |
| GET | `/api/resumes?job_id=` | | versions, newest first |
| GET / DELETE | `/api/resumes/{version_id}` | | |
| GET | `/api/resumes/{version_id}/comparison` | | original vs tailored text and per-bullet token diffs |
| GET | `/api/resumes/{version_id}/revisions` | | the optimisation cycles behind this version |
| POST | `/api/resumes/{version_id}/edits` | `{"ops": [...]}` | creates a new version (see below) |
| POST | `/api/resumes/{version_id}/approve` | | refused while any claim is unsupported |
| GET | `/api/resumes/{version_id}/preview.png?page=1&dpi=130` | | page image of the PDF |
| GET | `/api/resumes/{version_id}/export.zip` | | every file of the version |
| GET | `/api/files/{file_id}?inline=1` | | one generated file |

Edit operations (applied in order, then the version is re-rendered and re-validated):

```json
{"ops": [
  {"op": "set_bullet_text", "bullet_id": "b-…", "text": "New wording"},
  {"op": "remove_bullet", "bullet_id": "b-…"},
  {"op": "move_bullet", "bullet_id": "b-…", "to": 0},
  {"op": "restore_bullet", "achievement_id": "ach-…"},
  {"op": "approve_bullet", "bullet_id": "b-…"},
  {"op": "set_target_title", "title": "Senior Data Analyst"}
]}
```

## Applications

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/applications` | | the pipeline: job, fit, latest and submitted versions, status |
| PUT | `/api/applications/{job_id}` | `status`, `resume_version_id`, `notes` | status: `not_applied`, `applied`, `screening`, `interviewing`, `offer`, `rejected`, `withdrawn`, `archived`; `applied` records the date and the exact version sent |

## Agent integration

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/agent/jobs/import` | `{"postings": [{"title", "company", "url", "location", "description"}]}` | batch intake from a job-search agent; duplicates are flagged |
| GET | `/api/agent/summary` | | profile summary and pipeline in one call |

The same capabilities are available over MCP (`python -m app.mcp_server`); see the main README.

## Example

```bash
curl -s -F file=@master_resume.pdf http://127.0.0.1:8000/api/profile/import | jq .completeness
```

```bash
curl -s -H 'content-type: application/json' -d '{"text": "<paste the posting>"}' http://127.0.0.1:8000/api/jobs | jq '{id, duplicate}'
```

```bash
curl -s -H 'content-type: application/json' -d '{"job_id": "<id>"}' http://127.0.0.1:8000/api/resumes | jq .summary_scores
```
