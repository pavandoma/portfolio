"""MCP server exposing the platform to Claude Code, Codex or a job-search agent (stdio transport).

Runs locally against the same database as the web app. It never submits applications and never
sends resume data anywhere; it returns analysis, scores and the paths of generated files.

    python -m app.mcp_server
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.config import get_settings
from app.db import init_db, session_scope
from app.schemas.match import MatchReport
from app.services import applications, profiles, resumes
from app.services import jobs as job_service
from app.tailoring.presets import list_presets

server = MCPServer(
    "resume-intelligence-platform",
    instructions=("Evidence-based resume tooling. Analyse job postings against the user's verified master profile, "
                  "generate truthful tailored resumes, and track applications. Scores are heuristics computed by "
                  "this tool, not employer ATS scores. Never claims experience the profile does not contain."),
)


def _report_brief(report: MatchReport) -> dict[str, Any]:
    return {
        "job_fit": report.job_fit.total,
        "dimensions": {d.key: round(d.score, 3) for d in report.job_fit.dimensions},
        "strengths": report.strengths,
        "missing_mandatory": report.missing_mandatory,
        "missing_preferred": report.missing_preferred,
        "gates": [{"gate": g.gate, "status": g.status, "requirement": g.requirement_text} for g in report.gates],
        "recommendations": report.recommendations[:8],
        "disclaimer": report.disclaimer,
    }


@server.tool()
def profile_summary() -> dict[str, Any]:
    """Summarise the master profile: roles, skills, completeness and open verification issues."""
    with session_scope() as s:
        _p, rev, data = profiles.current(s)
        return {
            "name": data.personal.name, "revision": rev.revision_no,
            "roles": [f"{r.title}, {r.organization} ({r.date_text})" for r in data.roles],
            "projects": [f"{p.name} ({p.context})" for p in data.projects],
            "skills": sorted(data.skill_names()),
            "completeness": profiles.completeness(data),
            "open_issues": [i.message for i in data.issues if i.status == "open" and i.severity != "info"][:15],
        }


@server.tool()
def analyze_job(text: str = "", url: str = "", title: str = "", company: str = "") -> dict[str, Any]:
    """Analyse a job posting (pasted text or a URL). Duplicates of an existing job are detected and returned."""
    from app.ingest.url_fetch import fetch_job

    with session_scope() as s:
        if not text.strip() and url:
            fetched = fetch_job(url, get_settings())
            text, title, company = fetched.text, title or (fetched.title or ""), company or (fetched.company or "")
        if len(text.strip()) < 80:
            raise ValueError("Provide the full job description text or a fetchable URL.")
        job, dup = job_service.create_job(s, text, url=url or None, title=title or None, company=company or None)
        analysis = job_service.job_analysis(job)
        return {
            "job_id": job.id, "duplicate": dup, "title": analysis.title, "company": analysis.company,
            "location": analysis.location, "work_arrangement": analysis.work_arrangement,
            "seniority": analysis.seniority, "min_years": analysis.min_years_experience,
            "mandatory": [r.text for r in analysis.by_category("mandatory")][:15],
            "preferred": [r.text for r in analysis.by_category("preferred")][:10],
            "top_skills": [k.as_written for k in analysis.skill_importance[:10]],
            "injection_warnings": analysis.injection_warnings,
        }


@server.tool()
def match_job(job_id: str) -> dict[str, Any]:
    """Score the master profile against an analysed job (transparent, deterministic job-fit score)."""
    with session_scope() as s:
        _rec, report = job_service.run_match(s, job_id)
        return _report_brief(report)


@server.tool()
def generate_resume(job_id: str = "", variant: str = "") -> dict[str, Any]:
    """Generate, validate and save a tailored resume for a job (or a variant key from list_variants)."""
    with session_scope() as s:
        v = resumes.generate(s, get_settings(), job_id=job_id or None, variant=variant or None)
        sc = v.scores
        return {
            "resume_version_id": v.id, "version_no": v.version_no, "status": v.status,
            "scores": {"job_fit": sc["job_fit"]["total"], "resume_alignment": sc["resume_alignment"]["total"],
                       "ats_parsing": sc["ats_parsing"], "evidence_integrity": sc["evidence_integrity"],
                       "qa": sc["qa"], "critical_issues": sc["critical_issues"]},
            "needs_approval": sum(1 for c in v.change_log if c.get("requires_approval")),
            "files": {f.kind: f.path for f in v.files},
        }


@server.tool()
def list_variants() -> list[dict[str, Any]]:
    """Reusable resume target categories (AI Engineer, Data Analyst, ...)."""
    return list_presets()


@server.tool()
def list_applications() -> list[dict[str, Any]]:
    """The application pipeline: jobs, fit scores, resume versions and statuses."""
    with session_scope() as s:
        rows = applications.overview(s)
        for r in rows:
            for k in ("analyzed_at", "applied_at"):
                r[k] = r[k].isoformat() if r[k] else None
        return rows


@server.tool()
def update_application(job_id: str, status: str = "", resume_version_id: str = "", notes: str = "") -> dict[str, Any]:
    """Record an application status (the user applies themselves; this tool never submits anything)."""
    with session_scope() as s:
        app = applications.upsert(s, job_id, status=status or None, resume_version_id=resume_version_id or None,
                                  notes=notes or None)
        return {"job_id": app.job_id, "status": app.status, "resume_version_id": app.resume_version_id}


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    get_settings().ensure_dirs()
    init_db()
    server.run()


if __name__ == "__main__":
    main()
