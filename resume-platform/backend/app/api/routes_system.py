"""System status, variants, background tasks, data deletion and the agent-integration API."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import __version__, models
from app.config import get_settings
from app.db import Base, get_engine, get_session
from app.llm.factory import describe as describe_llm
from app.services import applications, jobs as job_service, profiles, tasks
from app.tailoring.presets import list_presets
from app.validation.adapters.registry import describe_adapters
from app.validation.ats import pdftotext_available

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.get("/system/status")
def status(session: Session = Depends(get_session)):
    s = get_settings()
    try:
        _p, rev, data = profiles.current(session)
        profile = {"exists": True, "revision": rev.revision_no, "name": data.personal.name,
                   "completeness": profiles.completeness(data)}
    except profiles.NotFound:
        profile = {"exists": False}
    return {
        "version": __version__,
        "database": "postgresql" if s.resolved_database_url.startswith("postgres") else "sqlite",
        "llm": describe_llm(s),
        "validators": describe_adapters(),
        "pdftotext": pdftotext_available(),
        "firecrawl_configured": bool(s.firecrawl_api_key),
        "external_data_sharing": s.allow_external_data_sharing,
        "auth_required": bool(s.api_token),
        "profile": profile,
        "counts": {
            "jobs": session.query(models.Job).count(),
            "resume_versions": session.query(models.ResumeVersion).count(),
            "applications": session.query(models.Application).count(),
        },
    }


@router.get("/variants")
def variants():
    return list_presets()


@router.get("/tasks/{task_id}")
def task_status(task_id: str):
    t = tasks.get(task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return t


class PurgeRequest(BaseModel):
    confirm: str = Field(description='Type "DELETE ALL MY DATA" to confirm.')


@router.post("/system/purge")
def purge(body: PurgeRequest, session: Session = Depends(get_session)):
    """User-controlled deletion of every document, profile, job, resume and file."""
    if body.confirm != "DELETE ALL MY DATA":
        raise HTTPException(400, 'Confirmation text must be exactly "DELETE ALL MY DATA".')
    s = get_settings()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.commit()
    for d in (s.uploads_dir, s.outputs_dir):
        shutil.rmtree(d, ignore_errors=True)
    s.ensure_dirs()
    return {"deleted": True}


# --------------------------------------------------------------------------- agent integration


class AgentPosting(BaseModel):
    title: str | None = None
    company: str | None = None
    url: str | None = None
    location: str | None = None
    description: str = Field(min_length=40, max_length=100_000)


class AgentImport(BaseModel):
    postings: list[AgentPosting] = Field(max_length=50)


@router.post("/agent/jobs/import", tags=["agent"])
def agent_import(body: AgentImport, session: Session = Depends(get_session)):
    """For a job-search agent: import postings (deduplicated by URL / company+title / text)."""
    out = []
    for p in body.postings:
        text = p.description
        if p.location and p.location not in text:
            text = f"Location: {p.location}\n{text}"
        job, dup = job_service.create_job(session, text, url=p.url, title=p.title, company=p.company)
        out.append({"job_id": job.id, "duplicate": dup, "title": job.title, "company": job.company})
    return {"imported": out}


@router.get("/agent/summary", tags=["agent"])
def agent_summary(session: Session = Depends(get_session)):
    """Compact state for an orchestrating agent: profile readiness and the application pipeline."""
    try:
        _p, rev, data = profiles.current(session)
        prof = {"name": data.personal.name, "revision": rev.revision_no, "completeness": profiles.completeness(data),
                "roles": [f"{r.title}, {r.organization}" for r in data.roles],
                "skills": sorted(data.skill_names())[:60]}
    except profiles.NotFound:
        prof = None
    return {"profile": prof, "pipeline": applications.overview(session)}


@router.get("/audit", tags=["system"])
def audit_log(limit: int = 200, session: Session = Depends(get_session)):
    rows = session.scalars(select(models.AuditEvent).order_by(models.AuditEvent.created_at.desc()).limit(min(limit, 1000)))
    return [{"id": r.id, "entity_type": r.entity_type, "entity_id": r.entity_id, "action": r.action, "actor": r.actor,
             "detail": r.detail, "created_at": r.created_at} for r in rows]


def _engine_ok() -> bool:  # pragma: no cover - used by docker healthchecks
    return get_engine() is not None
