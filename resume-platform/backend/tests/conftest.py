from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

FIXTURES = BACKEND / "tests" / "fixtures"
JOB_FIXTURES = FIXTURES / "jobs"
# The real master resume contains personal contact details and is kept out of the public
# repository. Tests that need it look here and are skipped when it is absent.
REAL_RESUME = Path(os.environ.get("RIP_TEST_RESUME_PDF", BACKEND.parent / "data" / "inputs" / "master_resume.pdf"))
TODAY = date(2026, 10, 28)

needs_real_resume = pytest.mark.skipif(not REAL_RESUME.exists(), reason="real master resume not available")


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own data dir and SQLite database."""
    from app.config import reset_settings_cache
    from app.db import reset_engine

    monkeypatch.setenv("RIP_IGNORE_ENV_FILE", "1")  # a developer's .env must not leak into tests
    monkeypatch.setenv("RIP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.delenv("RIP_API_TOKEN", raising=False)
    monkeypatch.delenv("RIP_MCP_CONFIG", raising=False)
    reset_settings_cache()
    reset_engine()
    yield
    reset_engine()
    reset_settings_cache()


def job_text(name: str) -> str:
    return (JOB_FIXTURES / f"{name}.txt").read_text(encoding="utf-8")


@pytest.fixture
def synthetic_pdf() -> bytes:
    from tests.synthetic_resume import build_synthetic_resume_pdf

    return build_synthetic_resume_pdf()


@pytest.fixture
def synthetic_docx() -> bytes:
    from tests.synthetic_resume import build_synthetic_resume_docx

    return build_synthetic_resume_docx()


@pytest.fixture
def synthetic_profile(synthetic_pdf):
    from app.ingest.extract import extract_pdf
    from app.ingest.profile_builder import build_profile
    from app.ingest.resume_parser import parse_resume

    return build_profile(parse_resume(extract_pdf(synthetic_pdf)), document_id="doc-synth",
                         document_name="synthetic.pdf", today=TODAY)


@pytest.fixture
def real_pdf() -> bytes:
    if not REAL_RESUME.exists():
        pytest.skip("real master resume not available")
    return REAL_RESUME.read_bytes()


@pytest.fixture
def real_profile(real_pdf):
    from app.ingest.extract import extract_pdf
    from app.ingest.profile_builder import build_profile
    from app.ingest.resume_parser import parse_resume

    return build_profile(parse_resume(extract_pdf(real_pdf)), document_id="doc-real", document_name="master_resume.pdf",
                         today=TODAY)
