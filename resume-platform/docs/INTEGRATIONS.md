# Integrations

Everything here is optional. With no keys and `LLM_PROVIDER=none`, the platform runs fully offline and
deterministically. The status of each integration is shown on the dashboard (`GET /api/system/status`).

**Data-sharing rule.** Profile and resume text is sent to a third party only when you set
`RIP_ALLOW_EXTERNAL_DATA_SHARING=true` *and* configure that service. Local services (Ollama, validators
marked `local_only`) do not need the flag. Job posting text you supply or fetch is not personal data, but
it is still treated as untrusted input everywhere.

## Language models (`app/llm/`)

| `LLM_PROVIDER` | Settings | Notes |
|---|---|---|
| `none` (default) | | all features work; no wording suggestions |
| `anthropic` | `ANTHROPIC_API_KEY`, optional `LLM_MODEL` (default `claude-opus-5-5`) | official `anthropic` SDK, structured JSON output via a JSON schema |
| `openai` | `OPENAI_API_KEY`, `LLM_MODEL`, optional `OPENAI_BASE_URL` | Chat Completions with `response_format: json_schema`; any compatible endpoint |
| `ollama` | `LLM_MODEL`, `OLLAMA_BASE_URL` | local; counts as on-device, so no sharing flag needed |

What a model is allowed to do:

- **Suggest wording** for an achievement (`POST /api/profile/achievements/{id}/suggest`). Every suggestion
  goes through the same fact check as any other variant and stays pending until you approve it. A
  suggestion that adds a number, tool, employer or claim is stored as failed and cannot be used.
- **Re-check requirement categories** of a posting (`POST /api/jobs/{id}/refine`). An answer is accepted
  only when it quotes the posting verbatim; the deterministic parser stays the fallback.

A model never scores, never chooses what goes on the resume, and never writes resume text directly.
Prompt-injection lines found in a posting are removed before any model call, and posting text is
wrapped as untrusted data.

**Verification status:** the three providers are tested against mocked HTTP endpoints (request shape,
structured output parsing, refusals, errors, the sharing gate). No live call was made while building.

## Job postings by URL (`app/ingest/url_fetch.py`)

| `fetch_with` | Behaviour |
|---|---|
| `auto` (default) | Firecrawl when `FIRECRAWL_API_KEY` is set, else the built-in fetcher |
| `builtin` | direct HTTP GET: public IPs only, redirects followed manually (max 4) and re-checked, size and time caps, schema.org `JobPosting` JSON-LD used when present |
| `firecrawl` | Firecrawl v2 `POST /v2/scrape` with `formats: ["markdown"]`, `onlyMainContent: true` |

Many job boards (LinkedIn, Indeed) block automated fetching or require sign-in. When a fetch fails or
returns too little text, paste the posting instead. Firecrawl receives only the URL.

## GitHub evidence (`app/ingest/github.py`)

`POST /api/profile/evidence/github` reads a public repository's metadata, languages, topics and README
through the GitHub REST API and attaches it as evidence to the best-matching project. `GITHUB_TOKEN` is
optional and only raises the rate limit. Repository evidence supports existing claims; it never adds
bullets on its own.

## External validators over MCP (`app/validation/adapters/`)

Built-in validators always run: the PyMuPDF parser, the python-docx parser and, when installed, poppler's
`pdftotext`. External validators are loaded from the JSON file named by `RIP_MCP_CONFIG`; see
[`examples/mcp-validators.example.json`](../examples/mcp-validators.example.json).

```jsonc
{
  "name": "my-parser",
  "category": "parser",            // parser | matcher
  "transport": "stdio",            // stdio (command + args) | http (url)
  "command": "python", "args": ["server.py"],
  "tool": "parse_resume",
  "arguments": {"resume_text": "{resume_text}", "job_text": "{job_text}"},
  "score_path": "score",           // where the score is in the tool's structured result
  "allow_resume_data": true,       // must be true to send resume text at all
  "local_only": true,              // runs on this machine; exempt from the sharing flag
  "enabled": true
}
```

Rules the adapter enforces:

- A tool that would receive resume text is skipped unless `allow_resume_data` is true and either
  `local_only` is true or `RIP_ALLOW_EXTERNAL_DATA_SHARING=true`. Skips are reported with the reason.
- External scores are shown exactly as returned, labelled with the tool's name, and never mixed into this
  platform's scores.
- When no external matcher is configured, the report lists one as **unavailable** instead of estimating a
  score.

### Services researched

| Service | Status |
|---|---|
| HireLayer MCP (`npx -y hirelayer-mcp`) | Verified to exist: official, MIT-licensed, maintained. Needs `HIRELAYER_API_KEY`. Stores parsed resumes in your account (Paris, France) unless `do_not_store_data` is passed. **Not connected or tested**; the argument names of `score_resumes` are unverified, so the example entry is disabled. Run `tools/list` against it and confirm the schema before enabling. |
| Jobscan, Teal | No public API or MCP server found. Not integrated. |
| Rezi, Reactive Resume, run-llama and community "resume MCP" servers | Exist in various forms; not verified or integrated. |

## This platform as an MCP server (`app/mcp_server.py`)

Claude Code, Codex or a job-search agent can drive the platform over stdio. Tools: `profile_summary`,
`analyze_job` (text or URL; duplicates detected), `match_job`, `generate_resume` (job or variant),
`list_variants`, `list_applications`, `update_application`. It shares the web app's database, returns
local file paths, and never submits applications or sends resume data anywhere. Configuration snippets
for Claude Code and Codex are in the main [README](../README.md#use-it-from-claude-code-or-codex-mcp). The
end-to-end test `tests/test_phase5_e2e.py::test_platform_mcp_server_over_stdio` exercises every tool over a
real stdio connection.

## Agent intake over HTTP

`POST /api/agent/jobs/import` accepts a batch of postings from any job-search agent, analyses each one and
flags duplicates (by canonical URL, then company + title + location, then text). `GET /api/agent/summary`
returns the profile summary and pipeline in one call.
