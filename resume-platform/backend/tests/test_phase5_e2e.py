"""Phase 5: end-to-end smoke tests against real processes.

* the backend served by uvicorn, driven over HTTP;
* the Next.js frontend (when built) proxying to that backend;
* the platform's own MCP server over stdio, as Claude Code or Codex would launch it;
* Alembic migrations, on SQLite always and on PostgreSQL when RIP_TEST_POSTGRES_URL is set.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest

from tests.conftest import BACKEND, job_text

FRONTEND = BACKEND.parent / "frontend"
pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _env(data_dir: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RIP_", "LLM_", "DATABASE_URL"))}
    env.update({"RIP_IGNORE_ENV_FILE": "1", "RIP_DATA_DIR": str(data_dir), "LLM_PROVIDER": "none"}, **extra)
    return env


def _wait(url: str, proc: subprocess.Popen, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise TimeoutError(url)


@contextmanager
def _process(cmd: list[str], *, cwd: Path, env: dict[str, str], ready_url: str, log: Path):
    with log.open("wb") as fh:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT)
        try:
            _wait(ready_url, proc)
            yield proc
        except Exception:
            proc.terminate()
            proc.wait(10)
            print(log.read_text(errors="replace")[-4000:])
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()


def _frontend_command(port: int) -> list[str] | None:
    node = shutil.which("node")
    next_bin = FRONTEND / "node_modules" / "next" / "dist" / "bin" / "next"
    if not node or not next_bin.exists() or not (FRONTEND / ".next" / "BUILD_ID").exists():
        return None
    return [node, str(next_bin), "start", "--port", str(port), "--hostname", "127.0.0.1"]


def test_servers_end_to_end(tmp_path, synthetic_pdf):
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    backend_cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]
    with _process(backend_cmd, cwd=BACKEND, env=_env(tmp_path / "data"), ready_url=f"{base}/api/health",
                  log=tmp_path / "backend.log"):
        c = httpx.Client(base_url=base, timeout=60)
        r = c.post("/api/profile/import", files={"file": ("cv.pdf", synthetic_pdf, "application/pdf")})
        assert r.status_code == 200, r.text
        job = c.post("/api/jobs", json={"text": job_text("data_engineer")}).json()
        report = c.post(f"/api/jobs/{job['id']}/match").json()["report"]
        assert 0 < report["job_fit"]["total"] < 100
        version = c.post("/api/resumes", json={"job_id": job["id"]}).json()
        assert version["summary_scores"]["evidence_integrity"] == 100.0
        pdf_url = next(f["url"] for f in version["files"] if f["kind"] == "pdf")
        assert c.get(pdf_url).content.startswith(b"%PDF")

        cmd = _frontend_command(fport := _free_port())
        if cmd is None:
            pytest.skip("frontend not built (run `npm ci && npm run build` in frontend/); backend checks passed")
        fbase = f"http://127.0.0.1:{fport}"
        fenv = {**os.environ, "BACKEND_URL": base, "PORT": str(fport), "NEXT_TELEMETRY_DISABLED": "1"}
        with _process(cmd, cwd=FRONTEND, env=fenv, ready_url=f"{fbase}/api/health", log=tmp_path / "frontend.log"):
            f = httpx.Client(base_url=fbase, timeout=60)
            assert f.get("/api/health").json()["status"] == "ok"  # proxied to the backend
            for page in ("/", "/profile", "/jobs/new", f"/jobs/{job['id']}", f"/resumes/{version['id']}",
                         "/resumes", "/applications"):
                assert f.get(page).status_code == 200, page
            # Binary downloads survive the proxy unchanged.
            via_proxy = f.get(pdf_url)
            assert via_proxy.headers["content-type"] == "application/pdf"
            assert via_proxy.content == c.get(pdf_url).content
            # Multipart upload through the proxy.
            r = f.post("/api/profile/import", files={"file": ("cv.pdf", synthetic_pdf, "application/pdf")})
            assert r.status_code == 200 and r.json()["revision"]["number"] == 2


def test_platform_mcp_server_over_stdio(tmp_path, synthetic_pdf):
    from mcp import Client, StdioServerParameters

    from app.config import get_settings
    from app.core.security import validate_upload
    from app.db import init_db, session_scope
    from app.services import profiles

    # Seed the profile in the same data directory the MCP server process will use.
    data_dir = get_settings().data_dir
    init_db()
    with session_scope() as s:
        profiles.import_resume(s, get_settings(), validate_upload("cv.pdf", synthetic_pdf, get_settings()))

    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND),
                                   env=_env(data_dir))

    async def run():
        async with Client(params, read_timeout_seconds=120) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            assert {"profile_summary", "analyze_job", "match_job", "generate_resume", "list_variants",
                    "list_applications", "update_application"} <= names
            summary = (await client.call_tool("profile_summary", {})).structured_content
            assert summary["name"] == "Jordan Avery Lee"
            job = (await client.call_tool("analyze_job", {"text": job_text("ai_engineer")})).structured_content
            fit = (await client.call_tool("match_job", {"job_id": job["job_id"]})).structured_content
            assert 0 < fit["job_fit"] < 100 and fit["disclaimer"]
            gen = (await client.call_tool("generate_resume", {"job_id": job["job_id"]})).structured_content
            assert gen["scores"]["evidence_integrity"] == 100.0
            assert Path(gen["files"]["pdf"]).read_bytes().startswith(b"%PDF")
            upd = (await client.call_tool("update_application", {
                "job_id": job["job_id"], "status": "applied", "resume_version_id": gen["resume_version_id"]})).structured_content
            assert upd["status"] == "applied"
            bad = await client.call_tool("match_job", {"job_id": "does-not-exist"})
            assert bad.is_error

    asyncio.run(run())


def _alembic(*args: str, env: dict[str, str]) -> str:
    out = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
    return out.stdout + out.stderr


def _migration_round_trip(env: dict[str, str]) -> None:
    _alembic("upgrade", "head", env=env)
    # The migration matches the ORM models exactly (no pending autogenerate operations).
    assert "No new upgrade operations detected" in _alembic("check", env=env)
    _alembic("downgrade", "base", env=env)
    _alembic("upgrade", "head", env=env)


def test_migrations_sqlite(tmp_path):
    _migration_round_trip(_env(tmp_path / "data"))


@pytest.mark.skipif(not os.environ.get("RIP_TEST_POSTGRES_URL"), reason="set RIP_TEST_POSTGRES_URL to test PostgreSQL")
def test_migrations_and_workflow_postgres(tmp_path, monkeypatch, synthetic_pdf):
    """Run against a disposable database: the test drops all platform tables at the end."""
    from fastapi.testclient import TestClient

    from app.config import reset_settings_cache
    from app.db import reset_engine

    url = os.environ["RIP_TEST_POSTGRES_URL"]
    env = _env(tmp_path / "data", DATABASE_URL=url)
    _migration_round_trip(env)

    monkeypatch.setenv("DATABASE_URL", url)
    reset_settings_cache()
    reset_engine()
    from app.main import create_app

    try:
        with TestClient(create_app()) as c:
            assert c.post("/api/profile/import",
                          files={"file": ("cv.pdf", synthetic_pdf, "application/pdf")}).status_code == 200
            job = c.post("/api/jobs", json={"text": job_text("ml_engineer")}).json()
            v = c.post("/api/resumes", json={"job_id": job["id"]}).json()
            v2 = c.post(f"/api/resumes/{v['id']}/edits", json={"ops": [
                {"op": "remove_bullet", "bullet_id": v["content"]["experience"][0]["bullets"][-1]["id"]}]}).json()
            assert v2["version_no"] == 2
            assert c.post(f"/api/resumes/{v['id']}/approve").json()["status"] == "approved"
            assert c.put(f"/api/applications/{job['id']}",
                         json={"status": "applied", "resume_version_id": v["id"]}).status_code == 200
            assert len(c.get("/api/audit").json()) >= 3
            assert c.post("/api/system/purge", json={"confirm": "DELETE ALL MY DATA"}).json()["deleted"]
    finally:
        reset_engine()
        _alembic("downgrade", "base", env=env)
