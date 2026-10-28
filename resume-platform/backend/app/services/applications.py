"""Application tracker: one record per job, linked to the exact resume version submitted."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Job, MatchRecord, ResumeVersion
from app.services.profiles import NotFound, audit

STATUSES = ["not_applied", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn", "archived"]


def upsert(session: Session, job_id: str, *, status: str | None = None, resume_version_id: str | None = None,
           notes: str | None = None, applied_at: datetime | None = None) -> Application:
    job = session.get(Job, job_id)
    if not job:
        raise NotFound("Job not found")
    app = session.scalars(select(Application).where(Application.job_id == job_id)).first()
    before = None
    if app is None:
        app = Application(job_id=job_id)
        session.add(app)
    else:
        before = {"status": app.status, "resume_version_id": app.resume_version_id}
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(STATUSES)}")
        app.status = status
        if status == "applied" and app.applied_at is None:
            from app.schemas.common import utcnow

            app.applied_at = applied_at or utcnow()
    if resume_version_id is not None:
        v = session.get(ResumeVersion, resume_version_id)
        if not v or v.job_id != job_id:
            raise ValueError("That resume version does not belong to this job.")
        app.resume_version_id = resume_version_id
    elif status == "applied" and app.resume_version_id is None:
        # Record which version went out: the latest approved one, else the latest generated one.
        versions = session.scalars(select(ResumeVersion).where(ResumeVersion.job_id == job_id)
                                   .order_by(ResumeVersion.version_no.desc())).all()
        chosen = next((v for v in versions if v.status == "approved"), versions[0] if versions else None)
        if chosen:
            app.resume_version_id = chosen.id
    if notes is not None:
        app.notes = notes[:10000]
    if applied_at is not None:
        app.applied_at = applied_at
    session.flush()
    audit(session, "application", app.id, "updated", {"before": before, "status": app.status,
                                                     "resume_version_id": app.resume_version_id})
    return app


def overview(session: Session) -> list[dict]:
    rows = []
    jobs = session.scalars(select(Job).where(Job.duplicate_of.is_(None)).order_by(Job.created_at.desc()))
    for job in jobs:
        app = session.scalars(select(Application).where(Application.job_id == job.id)).first()
        match = session.scalars(select(MatchRecord).where(MatchRecord.job_id == job.id)
                                .order_by(MatchRecord.created_at.desc())).first()
        versions = list(session.scalars(select(ResumeVersion).where(ResumeVersion.job_id == job.id)
                                        .order_by(ResumeVersion.version_no.desc())))
        latest = versions[0] if versions else None
        rows.append({
            "job_id": job.id, "title": job.title, "company": job.company, "location": job.location, "url": job.url,
            "analyzed_at": job.created_at, "job_fit": match.job_fit if match else None,
            "resume_versions": len(versions),
            "latest_version_id": latest.id if latest else None,
            "latest_alignment": (latest.scores.get("resume_alignment") or {}).get("total") if latest else None,
            "latest_status": latest.status if latest else None,
            "application_status": app.status if app else "not_applied",
            "submitted_version_id": app.resume_version_id if app else None,
            "applied_at": app.applied_at if app else None,
            "notes": app.notes if app else "",
        })
    return rows
