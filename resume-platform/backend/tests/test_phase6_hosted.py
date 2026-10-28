"""Phase 6: hosted mode (Vercel) — files in the database, migrations on start, refusal without a token or a
database, Postgres URL handling, and the dependency list Vercel installs."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, reset_settings_cache
from app.db import reset_engine
from tests.conftest import BACKEND, job_text


def _client(monkeypatch, **env: str) -> TestClient:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    reset_settings_cache()
    reset_engine()
    from app.main import create_app

    return TestClient(create_app())


def test_files_survive_a_new_server_instance(monkeypatch, synthetic_pdf):
    """RIP_STORAGE=db: a server without the local files (another Vercel instance) serves them from the database."""
    with _client(monkeypatch, RIP_STORAGE="db", RIP_AUTO_MIGRATE="1") as c:
        assert c.post("/api/profile/import", files={"file": ("cv.pdf", synthetic_pdf, "application/pdf")}).status_code == 200
        job = c.post("/api/jobs", json={"text": job_text("data_analyst")}).json()
        v = c.post("/api/resumes", json={"job_id": job["id"]}).json()
        pdf_url = next(f["url"] for f in v["files"] if f["kind"] == "pdf")
        original = c.get(pdf_url).content

        from app.config import get_settings

        data_dir = get_settings().data_dir
        shutil.rmtree(data_dir / "outputs")
        shutil.rmtree(data_dir / "uploads")
        assert c.get(pdf_url).content == original
        assert c.get(f"/api/resumes/{v['id']}/preview.png").headers["content-type"] == "image/png"
        assert c.get(f"/api/resumes/{v['id']}/export.zip").status_code == 200

        from sqlalchemy import func, select

        from app.db import session_scope
        from app.models import StoredFile

        def stored() -> int:
            with session_scope() as s:
                return s.scalar(select(func.count()).select_from(StoredFile))

        before = stored()
        assert before >= len(v["files"]) + 1  # every generated file plus the uploaded resume
        assert c.delete(f"/api/resumes/{v['id']}").json()["deleted"]
        assert stored() == before - len(v["files"])
        assert c.post("/api/system/purge", json={"confirm": "DELETE ALL MY DATA"}).json()["deleted"]
        assert stored() == 0


def test_auto_migrate_creates_the_versioned_schema(monkeypatch):
    with _client(monkeypatch, RIP_AUTO_MIGRATE="1") as c:
        assert c.get("/api/system/status").status_code == 200
        from sqlalchemy import text

        from app.db import get_engine

        with get_engine().connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"


def test_refuses_without_token_or_database(monkeypatch):
    with _client(monkeypatch, RIP_REQUIRE_TOKEN="1", RIP_EXPOSE_DOCS="0") as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/profile").status_code == 503
        assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    import app.config as config

    monkeypatch.setattr(config, "ON_VERCEL", True)
    with _client(monkeypatch, RIP_API_TOKEN="a-long-enough-token") as c:
        r = c.get("/api/profile", headers={"Authorization": "Bearer a-long-enough-token"})
        assert r.status_code == 503 and "DATABASE_URL" in r.json()["detail"]


@pytest.mark.parametrize("given, expected", [
    ("postgres://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
    ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
])
def test_postgres_urls_use_psycopg(given, expected):
    assert Settings(_env_file=None, DATABASE_URL=given).resolved_database_url == expected


def test_vercel_dependencies_match_requirements():
    """Vercel installs from pyproject.toml; local installs use requirements.txt. They must not drift."""
    pyproject = tomllib.loads((BACKEND / "pyproject.toml").read_text())
    requirements = [line.strip() for line in (BACKEND / "requirements.txt").read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
    assert pyproject["project"]["dependencies"] == requirements
    assert pyproject["tool"]["vercel"]["entrypoint"] == "app.main:app"
    assert Path(BACKEND / "app" / "main.py").exists()
