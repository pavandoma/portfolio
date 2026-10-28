"""Phase 3: ATS parse-back, evidence integrity, QA, revision loop and validator adapters."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.config import reset_settings_cache
from app.jobs.jd_parser import analyse_job
from app.matching.engine import score_profile, score_resume_alignment
from app.optimize.loop import optimize
from app.render.docx_writer import render_docx
from app.render.fit import fit_resume
from app.schemas.resume import ResumeHeader, TailoredResume
from app.tailoring.diff import resume_plain_text
from app.tailoring.tailor import TailorOptions, tailor
from app.validation import ats
from app.validation.adapters.base import ValidationContext
from app.validation.adapters.mcp_adapter import MCPServerConfig, MCPToolAdapter
from app.validation.adapters.registry import describe_adapters, run_all
from app.validation.integrity import check_integrity
from app.validation.qa import check_quality
from tests.conftest import TODAY, job_text

FAKE_MCP = Path(__file__).resolve().parent / "fixtures" / "mcp" / "fake_resume_parser_server.py"


@pytest.fixture
def generated(synthetic_profile):
    job = analyse_job(job_text("data_analyst"))
    report = score_profile(synthetic_profile, job, today=TODAY)
    tr = tailor(synthetic_profile, job, report, TailorOptions(today=TODAY))
    resume, pdf, _ = fit_resume(tr.resume)
    return synthetic_profile, job, report, resume, pdf, render_docx(resume)


def test_contact_dates_headings_survive_pdf_extraction(generated):
    _p, _j, _r, resume, pdf, docx = generated
    rep = ats.check_pdf(pdf, resume)
    by_field = {f.field: f for f in rep.fields}
    for key in ("name", "email", "phone", "link", "section_headings", "experience[0].dates", "experience[0].title",
                "experience[0].employer", "education[0]", "summary", "target_title"):
        assert by_field[key].status == "pass", (key, by_field[key])
    assert rep.score >= 95
    assert all(c.status != "fail" for c in rep.checks)


def test_docx_parse_back(generated):
    _p, _j, _r, resume, _pdf, docx = generated
    rep = ats.check_docx(docx, resume)
    assert rep.score >= 95, [f for f in rep.fields if f.status != "pass"]


@pytest.mark.skipif(not ats.pdftotext_available(), reason="poppler-utils not installed")
def test_independent_pdftotext_parse(generated):
    _p, _j, _r, resume, pdf, _docx = generated
    rep = ats.check_pdf_with_pdftotext(pdf, resume)
    assert rep is not None and rep.score >= 90


def test_integrity_clean_resume(generated):
    profile, _j, _r, resume, _pdf, _d = generated
    rep = check_integrity(profile, resume)
    assert rep.unsupported == 0 and rep.employment_facts_preserved
    assert rep.score == 100.0
    assert rep.unverified > 0  # nothing is verified yet; reported, not hidden


def test_integrity_catches_fabrication_and_changed_facts(generated):
    profile, _j, _r, resume, _pdf, _d = generated
    tampered = resume.model_copy(deep=True)
    tampered.experience[0].bullets[0].text = "Led a team of 12 analysts at Google, saving $4M with Kubernetes."
    tampered.experience[0].organization = "Google"
    tampered.skills[0].items.append("Rust")
    rep = check_integrity(profile, tampered)
    assert not rep.employment_facts_preserved
    assert rep.unsupported >= 3
    qa = check_quality(profile, tampered, integrity=rep)
    assert any(i.code == "unsupported_claim" and i.severity == "critical" for i in qa.issues)


def test_qa_flags_style_problems(generated):
    profile, job, report, resume, _pdf, _d = generated
    r = resume.model_copy(deep=True)
    r.experience[0].bullets[0].text = ("Responsible for leveraging cutting-edge synergies to deliver robust, seamless "
                                       "dashboards across the organization, ensuring stakeholder alignment.")
    qa = check_quality(profile, r, job, report)
    codes = {i.code for i in qa.issues}
    assert {"ai_tell", "weak_opener"} <= codes


def test_alignment_scorecard(generated):
    profile, job, _r, resume, _pdf, _d = generated
    card = score_resume_alignment(profile, job, resume, ats_score=100, qa_score=90)
    assert [d.key for d in card.dimensions] == ["required", "experience", "keywords", "impact", "ats", "clarity"]
    assert 0 <= card.total <= 100
    again = score_resume_alignment(profile, job, resume, ats_score=100, qa_score=90)
    assert card.model_dump() == again.model_dump()


def test_revision_loop_removes_academic_production_claim(synthetic_profile):
    profile = synthetic_profile.model_copy(deep=True)
    proj = profile.projects[0]
    proj.context = "academic"
    ach = proj.achievements[0]
    ach.text = ach.original_text = "Launched a production-grade enterprise forecasting platform used by real users."
    ach.variants = []
    ach.technologies, ach.competencies = [], []
    job = analyse_job(job_text("ml_engineer"))
    report = score_profile(profile, job, today=TODAY)
    result = optimize(profile, job, report, TailorOptions(today=TODAY), max_cycles=3)
    assert 1 <= len(result.iterations) <= 3
    final_text = " ".join(b.text for b in result.final.resume.all_bullets()).lower()
    assert "production-grade" not in final_text and "enterprise" not in final_text
    assert result.final.critical == 0
    for it in result.iterations:
        assert set(it.scores()) >= {"resume_alignment", "ats_parsing", "evidence_integrity", "qa"}


def test_loop_stops_without_critical_issues(synthetic_profile):
    job = analyse_job(job_text("data_analyst"))
    result = optimize(synthetic_profile, job, score_profile(synthetic_profile, job, today=TODAY),
                      TailorOptions(today=TODAY))
    assert result.stop_reason in ("no_critical_issues", "no_further_improvement")
    assert len(result.iterations) <= 3


def test_missing_external_services_do_not_break(generated, monkeypatch, tmp_path):
    _p, job, _r, resume, pdf, docx = generated
    ctx = ValidationContext(resume=resume, resume_text=resume_plain_text(resume), pdf=pdf, docx=docx, job=job,
                            job_text="")
    # No config at all.
    results = run_all(ctx)
    ext = [r for r in results if r.category == "matcher"]
    assert ext and ext[0].status == "unavailable" and ext[0].score is None
    # Broken config file and an unreachable server.
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"servers": [
        {"name": "ghost", "category": "matcher", "command": "/nonexistent/server", "tool": "match",
         "allow_resume_data": True, "local_only": True},
        {"name": "bad-entry"},
    ]}))
    monkeypatch.setenv("RIP_MCP_CONFIG", str(cfg))
    reset_settings_cache()
    results = run_all(ctx)
    ghost = next(r for r in results if r.adapter == "mcp:ghost")
    assert ghost.status == "unavailable" and ghost.score is None
    assert any(r.adapter == "internal-pymupdf" and r.status == "ok" for r in results)
    assert any("Invalid MCP entry" in d["detail"] for d in describe_adapters())


def test_mcp_adapter_against_local_server():
    r = TailoredResume(header=ResumeHeader(name="Test", target_title="X", contact=[]))
    ctx = ValidationContext(resume=r, resume_text="Jane jane@example.com builds dashboards", pdf=None, docx=None,
                            job=None, job_text="")
    cfg = MCPServerConfig(name="fake", tool="parse_resume", command=sys.executable, args=[str(FAKE_MCP)],
                          arguments={"resume_text": "{resume_text}"}, score_path="score", allow_resume_data=True,
                          local_only=True, timeout_s=60)
    ok = MCPToolAdapter(cfg).run(ctx)
    assert ok.status == "ok" and ok.score == 77.5 and ok.raw["email"] == "jane@example.com"
    denied = MCPToolAdapter(cfg.model_copy(update={"allow_resume_data": False})).run(ctx)
    assert denied.status == "not_authorized" and denied.score is None
    external = MCPToolAdapter(cfg.model_copy(update={"local_only": False})).run(ctx)
    assert external.status == "not_authorized"  # external sharing is off by default


def test_change_log_matches_fitted_resume(real_profile):
    """Content restored into free page space is logged like any other change, and never as removed."""
    import yaml

    from app.services.profiles import apply_pack_to_profile

    pack = Path(__file__).resolve().parents[2] / "examples" / "suggestion-packs" / "pavan-doma.yaml"
    apply_pack_to_profile(real_profile, yaml.safe_load(pack.read_text()))
    job = analyse_job(job_text("data_analyst"))
    result = optimize(real_profile, job, score_profile(real_profile, job, today=TODAY), TailorOptions(today=TODAY),
                      use_pdftotext=False)
    final = result.final.resume
    log = result.change_log
    reworded = {c.target for c in log if c.kind == "bullet_reworded"}
    removed = {c.target for c in log if c.kind in ("bullet_removed", "project_removed")}
    originals = {a.id: a.original_text for a, _ in real_profile.all_achievements()}
    for b in final.all_bullets():
        if b.text.rstrip(".") != originals[b.achievement_ids[0]].rstrip("."):
            assert b.id in reworded, b.text
        assert b.achievement_ids[0] not in removed
    assert not {p.name for p in final.projects} & removed
    # Pending approvals in the log match the unapproved bullets on the page.
    pending = {c.target for c in log if c.requires_approval and c.kind == "bullet_reworded"}
    assert pending == {b.id for b in final.all_bullets() if not b.approved}
