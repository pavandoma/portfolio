"""Phase 4: LLM adapters, URL fetching, Firecrawl, GitHub evidence and the platform MCP server."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from app.config import Settings, get_settings, reset_settings_cache
from app.core.security import UnsafeURLError
from app.ingest.github import best_project_match, fetch_repo, parse_repo_url
from app.ingest.url_fetch import FetchError, fetch_job
from app.jobs.jd_parser import analyse_job
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.llm.base import LLMNotConfigured, LLMRefusal
from app.llm.factory import get_provider
from app.llm.openai_provider import OllamaProvider, OpenAIProvider
from app.llm.tasks import refine_job_categories, suggest_wording


# --------------------------------------------------------------------------- fake Claude endpoint
class _FakeAnthropic(BaseHTTPRequestHandler):
    requests: list[dict] = []
    reply_text = "{}"
    stop_reason = "end_turn"

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        type(self).requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
        msg = {"id": "msg_test", "type": "message", "role": "assistant", "model": body["model"],
               "content": [{"type": "text", "text": type(self).reply_text}] if self.stop_reason != "refusal" else [],
               "stop_reason": type(self).stop_reason, "stop_sequence": None,
               "stop_details": {"type": "refusal", "category": "cyber", "explanation": "test"}
               if type(self).stop_reason == "refusal" else None,
               "usage": {"input_tokens": 12, "output_tokens": 34}}
        data = json.dumps(msg).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_claude():
    _FakeAnthropic.requests = []
    srv = HTTPServer(("127.0.0.1", 0), _FakeAnthropic)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_anthropic_provider_request_shape(fake_claude):
    _srv, url = fake_claude
    _FakeAnthropic.reply_text = json.dumps({"variants": ["Built dashboards in Tableau."], "summary_version": "x"})
    _FakeAnthropic.stop_reason = "end_turn"
    p = AnthropicProvider(api_key="test-key", base_url=url, timeout_s=10)
    out = p.complete_json(system="sys", user="usr", schema={"type": "object"}, max_tokens=500)
    assert out["variants"] == ["Built dashboards in Tableau."]
    req = _FakeAnthropic.requests[-1]
    assert req["path"].startswith("/v1/messages")
    assert FALLBACK_BETA in req["headers"].get("anthropic-beta", "")
    body = req["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "medium"
    assert "thinking" not in body  # thinking cannot be disabled on this model; it is simply omitted


def test_anthropic_refusal_is_reported(fake_claude):
    _srv, url = fake_claude
    _FakeAnthropic.stop_reason = "refusal"
    p = AnthropicProvider(api_key="test-key", base_url=url, timeout_s=10)
    with pytest.raises(LLMRefusal):
        p.complete_json(system="s", user="u", schema={"type": "object"})
    _FakeAnthropic.stop_reason = "end_turn"


def test_openai_and_ollama_providers():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.path] = json.loads(request.content)
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"ok": True})}}]})
        return httpx.Response(200, json={"message": {"content": json.dumps({"ok": 1})}})

    t = httpx.MockTransport(handler)
    assert OpenAIProvider("k", "some-model", transport=t).complete_json(system="s", user="u", schema={})["ok"] is True
    assert seen["/v1/chat/completions"]["response_format"]["type"] == "json_schema"
    assert OllamaProvider("llama3.1", transport=t).complete_json(system="s", user="u", schema={"type": "object"})["ok"] == 1
    assert seen["/api/chat"]["format"] == {"type": "object"}


def test_factory_blocks_external_sharing(monkeypatch):
    assert get_provider() is None  # default: LLM off
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    reset_settings_cache()
    with pytest.raises(LLMNotConfigured):
        get_provider()
    monkeypatch.setenv("RIP_ALLOW_EXTERNAL_DATA_SHARING", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    reset_settings_cache()
    assert get_provider().name == "anthropic"
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3.1")
    monkeypatch.setenv("RIP_ALLOW_EXTERNAL_DATA_SHARING", "false")
    reset_settings_cache()
    assert get_provider().is_local  # local models need no sharing permission


class _ScriptedLLM:
    name, model, is_local = "scripted", "test", True

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def complete_json(self, *, system, user, schema, max_tokens=4000):
        self.prompts.append((system, user))
        return self.reply


def test_llm_wording_is_fact_checked(synthetic_profile):
    ach, parent = synthetic_profile.all_achievements()[0]
    llm = _ScriptedLLM({"variants": [
        "Built weekly loan performance dashboards in Tableau with SQL views, saving 6 hours of manual reporting each week.",
        "Led a team of 8 analysts building Power BI dashboards that saved 20 hours per week.",
    ], "summary_version": "Cut manual reporting by 6 hours a week with Tableau dashboards."})
    kept, rejected = suggest_wording(llm, ach, parent)
    assert [v.origin for v in kept] == ["llm", "llm"]
    assert all(v.fact_check.passed and not v.approved for v in kept)
    assert len(rejected) == 1 and "Led a team" in rejected[0]["text"]
    assert "untrusted_document" in llm.prompts[0][1]  # source text is delimited as data


def test_llm_job_refinement_requires_verbatim_quotes():
    text = ("Junior Data Analyst\nWe value people who enjoy SQL and dashboards.\n"
            "Knowledge of Tableau would be useful for this team.\nWe sponsor visas.\n" + "x " * 30)
    job = analyse_job(text)
    inferred = [r for r in job.requirements if r.category_basis == "inferred"]
    assert inferred
    llm = _ScriptedLLM({"items": [
        {"quote": inferred[0].text, "category": "preferred"},
        {"quote": "A requirement the posting never says", "category": "mandatory"},
    ]})
    updated, changed = refine_job_categories(llm, job, text)
    first = next(r for r in updated.requirements if r.id == inferred[0].id)
    assert first.category == "preferred" and first.category_basis == "llm"
    assert changed <= 1


# --------------------------------------------------------------------------- URL fetching
@pytest.fixture
def fake_dns(monkeypatch):
    real = socket.getaddrinfo

    def resolver(host, port, *a, **k):
        table = {"jobs.example.com": "93.184.216.34", "internal.example.com": "10.1.2.3", "api.firecrawl.dev": "93.184.216.35"}
        if host in table:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (table[host], port))]
        return real(host, port, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", resolver)


JSONLD_PAGE = """<html><head><title>Careers</title>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"Data Analyst",
"hiringOrganization":{"@type":"Organization","name":"Example Corp"},
"jobLocation":{"@type":"Place","address":{"addressLocality":"Buffalo","addressRegion":"NY"}},
"description":"&lt;p&gt;Requirements&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Strong SQL skills&lt;/li&gt;&lt;li&gt;Experience with Tableau&lt;/li&gt;&lt;/ul&gt;"}</script>
</head><body><nav>menu</nav><h1>Data Analyst</h1><script>var x=1;</script></body></html>"""


def test_fetch_job_reads_jsonld(fake_dns):
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/posting/123"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text=JSONLD_PAGE)

    job = fetch_job("https://jobs.example.com/start", get_settings(), transport=httpx.MockTransport(handler))
    assert job.title == "Data Analyst" and job.company == "Example Corp" and job.location == "Buffalo, NY"
    assert "Strong SQL skills" in job.text and job.method == "builtin-jsonld"
    assert job.final_url.endswith("/posting/123")


def test_fetch_blocks_private_redirects(fake_dns):
    def handler(request):
        return httpx.Response(302, headers={"location": "http://internal.example.com/admin"})

    with pytest.raises(FetchError):
        fetch_job("https://jobs.example.com/x", get_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises((FetchError, UnsafeURLError)):
        fetch_job("http://internal.example.com/", get_settings())


def test_fetch_size_limit(fake_dns, monkeypatch):
    monkeypatch.setenv("RIP_FETCH_MAX_BYTES", "1000")
    reset_settings_cache()
    t = httpx.MockTransport(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, text="x" * 5000))
    with pytest.raises(FetchError):
        fetch_job("https://jobs.example.com/big", get_settings(), prefer="builtin", transport=t)


def test_firecrawl_sends_only_the_url(fake_dns):
    seen = {}

    def handler(request):
        if request.url.host == "api.firecrawl.dev":
            seen["auth"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"success": True, "data": {"markdown": "# Data Analyst\n" + "SQL " * 200,
                                                                       "metadata": {"title": "Data Analyst"}}})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><body>Loading...</body></html>")

    s = Settings(FIRECRAWL_API_KEY="fc-testkey1234567890")
    job = fetch_job("https://jobs.example.com/js-page", s, transport=httpx.MockTransport(handler))
    assert job.method == "firecrawl"
    assert seen["auth"] == "Bearer fc-testkey1234567890"
    assert seen["body"] == {"url": "https://jobs.example.com/js-page", "formats": ["markdown"], "onlyMainContent": True}


# --------------------------------------------------------------------------- GitHub evidence
def test_github_evidence(synthetic_profile):
    def handler(request):
        p = request.url.path
        if p == "/repos/jordan/streamlit-forecasting-app":
            return httpx.Response(200, json={"html_url": "https://github.com/jordan/streamlit-forecasting-app",
                                             "description": "Demand forecasting app with PyTorch and Docker",
                                             "topics": ["forecasting"], "stargazers_count": 3})
        if p.endswith("/languages"):
            return httpx.Response(200, json={"Python": 1000, "Dockerfile": 50})
        if p.endswith("/readme"):
            import base64

            return httpx.Response(200, json={"encoding": "base64",
                                             "content": base64.b64encode(b"Uses FastAPI and PyTorch").decode()})
        return httpx.Response(404)

    assert parse_repo_url("https://github.com/a/b.git") == ("a", "b")
    ev = fetch_repo("https://github.com/jordan/streamlit-forecasting-app", get_settings(),
                    transport=httpx.MockTransport(handler))
    assert {"PyTorch", "Docker", "FastAPI", "Python"} <= set(ev.technologies)
    project, score = best_project_match(ev, synthetic_profile.projects)
    assert project is not None and project.id == synthetic_profile.projects[0].id


# --------------------------------------------------------------------------- platform MCP server
def test_platform_mcp_server_in_process(synthetic_pdf):
    from mcp import Client

    from app.config import get_settings as gs
    from app.core.security import validate_upload
    from app.db import init_db, session_scope
    from app.mcp_server import server
    from app.services import profiles
    from tests.conftest import job_text

    init_db()
    with session_scope() as s:
        profiles.import_resume(s, gs(), validate_upload("cv.pdf", synthetic_pdf, gs()))

    async def run():
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert {"profile_summary", "analyze_job", "match_job", "generate_resume", "list_applications"} <= names
            summary = await client.call_tool("profile_summary", {})
            data = summary.structured_content
            assert data["name"] == "Jordan Avery Lee"
            job = (await client.call_tool("analyze_job", {"text": job_text("data_analyst")})).structured_content
            fit = (await client.call_tool("match_job", {"job_id": job["job_id"]})).structured_content
            assert 0 < fit["job_fit"] <= 100
            gen = (await client.call_tool("generate_resume", {"job_id": job["job_id"]})).structured_content
            assert gen["scores"]["evidence_integrity"] == 100.0 and gen["files"]["pdf"].endswith(".pdf")

    asyncio.run(run())
