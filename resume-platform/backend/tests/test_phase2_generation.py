"""Phase 2: recruiter-psychology tailoring, truthfulness rules and document generation."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
import yaml

from app.ingest.extract import extract_docx, extract_pdf
from app.jobs.jd_parser import analyse_job
from app.matching.engine import score_profile
from app.render.docx_writer import render_docx
from app.render.fit import fit_resume
from app.render.pdf_writer import page_count, render_pdf
from app.services.profiles import apply_pack_to_profile
from app.tailoring.diff import bullet_diffs, token_diff
from app.tailoring.presets import PRESETS, preset_job
from app.tailoring.rewrite import fact_check
from app.tailoring.style import ai_tells
from app.tailoring.tailor import TailorOptions, tailor
from tests.conftest import TODAY, job_text, needs_real_resume

PACK = Path(__file__).resolve().parents[2] / "examples" / "suggestion-packs" / "pavan-doma.yaml"


def _tailor(profile, name):
    job = analyse_job(job_text(name))
    report = score_profile(profile, job, today=TODAY)
    return tailor(profile, job, report, TailorOptions(today=TODAY)), job


def test_title_is_exact_posting_title(synthetic_profile):
    result, job = _tailor(synthetic_profile, "data_engineer")
    assert result.resume.header.target_title == "Data Engineer II"
    # Historical titles never change to match the posting.
    assert [e.title for e in result.resume.experience] == [r.title for r in synthetic_profile.roles]


def test_employment_facts_unchanged(synthetic_profile):
    for name in ("ai_engineer", "data_analyst", "ml_engineer"):
        result, _ = _tailor(synthetic_profile, name)
        for entry in result.resume.experience:
            role = next(r for r in synthetic_profile.roles if r.id == entry.role_id)
            assert entry.title == role.title
            assert entry.organization == role.organization
            assert entry.date_range == "Jun 2022 - Aug 2024" if role.title == "Data Analyst" else True


def test_every_claim_traces_to_profile(synthetic_profile):
    result, _ = _tailor(synthetic_profile, "data_analyst")
    ids = {a.id for a, _ in synthetic_profile.all_achievements()}
    for b in result.resume.all_bullets():
        assert b.achievement_ids and set(b.achievement_ids) <= ids
    for s in result.resume.summary:
        if s.kind == "result":
            assert s.source_ids and s.source_ids[0] in ids
    skill_ids = {s.id for s in synthetic_profile.skills}
    for line in result.resume.skills:
        for item in line.items:
            assert set(line.sources[item]) <= skill_ids


def test_no_unsupported_skills_added(synthetic_profile):
    result, job = _tailor(synthetic_profile, "data_engineer")
    listed = {i.lower() for line in result.resume.skills for i in line.items}
    # The posting asks for Snowflake and Airflow; the candidate has neither, so neither appears.
    assert "snowflake" not in listed and "apache airflow" not in listed and "airflow" not in listed


def test_resume_changes_between_roles(synthetic_profile):
    a, _ = _tailor(synthetic_profile, "data_analyst")
    b, _ = _tailor(synthetic_profile, "ml_engineer")
    assert a.resume.header.target_title != b.resume.header.target_title
    assert a.resume.summary_text != b.resume.summary_text
    assert [line.items for line in a.resume.skills] != [line.items for line in b.resume.skills]


def test_summary_follows_playbook(synthetic_profile):
    result, _ = _tailor(synthetic_profile, "data_analyst")
    s = result.resume.summary
    assert 2 <= len(s) <= 4
    assert s[0].text.startswith("Data Analyst")
    assert any(ch.isdigit() for ch in result.resume.summary_text), "summary should include one number"
    assert not ai_tells(result.resume.summary_text)


def test_pdf_and_docx_generated_and_extractable(synthetic_profile):
    result, _ = _tailor(synthetic_profile, "data_analyst")
    fitted, pdf, _actions = fit_resume(result.resume)
    assert pdf.startswith(b"%PDF") and page_count(pdf) == 1
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        text = d[0].get_text()
        assert not d[0].get_images()
    assert "JORDAN AVERY LEE" in text and "jordan.lee@example.com" in text
    assert "PROFESSIONAL EXPERIENCE" in text and "Jun 2022 - Aug 2024" in text
    docx_bytes = render_docx(fitted)
    lines = extract_docx(docx_bytes).text
    assert "Lakeview Credit Union" in lines and "jordan.lee@example.com" in lines


def test_page_fit_never_goes_below_minimum_font(synthetic_profile):
    result, _ = _tailor(synthetic_profile, "data_analyst")
    r = result.resume.model_copy(deep=True)
    # Inflate content to force overflow.
    for e in r.experience:
        e.bullets = e.bullets * 15
    fitted, pdf, actions = fit_resume(r)
    assert fitted.layout.body_font_size >= 9.5
    assert page_count(pdf) <= fitted.layout.page_target
    assert any("Removed" in a for a in actions)


def test_unapproved_wording_requires_approval(synthetic_profile):
    result, _ = _tailor(synthetic_profile, "data_analyst")
    reworded = [c for c in result.change_log if c.kind == "bullet_reworded"]
    for c in reworded:
        b = next(b for b in result.resume.all_bullets() if b.id == c.target)
        assert c.requires_approval == (not b.approved)


def test_fact_check_rejects_fabrication():
    src = ["Built weekly loan dashboards in Tableau, cutting manual reporting time by 6 hours per week."]
    assert fact_check("Built weekly loan dashboards in Tableau, cutting reporting time by 6 hours per week.", src).passed
    assert not fact_check("Built loan dashboards in Power BI, cutting reporting time by 8 hours.", src).passed
    assert not fact_check("Led a team of analysts building Tableau dashboards.", src).passed
    assert not fact_check("Built production dashboards for Google in Tableau.", src).passed


def test_diff_tokens():
    toks = token_diff("Built a dashboard in SQL.", "Built a KPI dashboard in SQL.")
    assert any(t.op == "insert" and "KPI" in t.text for t in toks)


def test_variants_presets_build(synthetic_profile):
    assert len(PRESETS) == 12
    for key in PRESETS:
        job = preset_job(key)
        result = tailor(synthetic_profile, job, None, TailorOptions(today=TODAY), variant=key)
        assert result.resume.header.target_title == PRESETS[key]["title"]
        assert result.resume.variant == key


@needs_real_resume
def test_real_resume_tailoring_with_suggestions(real_profile):
    pack = yaml.safe_load(PACK.read_text())
    results = apply_pack_to_profile(real_profile, pack)
    assert all(r.get("passed") for r in results), results
    result, _ = _tailor(real_profile, "ai_engineer")
    text = result.resume.summary_text + " " + " ".join(b.text for b in result.resume.all_bullets())
    # Academic projects must not claim production or enterprise use.
    for p in result.resume.projects:
        for b in p.bullets:
            assert "production" not in b.text.lower() and "enterprise" not in b.text.lower()
    assert result.resume.experience[0].title == "Data Engineer - Lead"
    assert result.resume.experience[0].date_range == "Sep 2024 - Dec 2025"
    assert not ai_tells(text)
    diffs = bullet_diffs(real_profile, result.resume)
    assert diffs and all(d.before for d in diffs)
    fitted, pdf, _ = fit_resume(result.resume, reserve_projects=result.reserve_projects,
                                reserve_bullets=result.reserve_bullets)
    assert page_count(pdf) == 1
    extracted = extract_pdf(pdf)
    assert "PAVAN SRINIVAS DOMA" in extracted.text
