"""Plain-dict views of ORM rows for API responses."""

from __future__ import annotations

from app.models import GeneratedFile, Job, ResumeVersion


def job_out(job: Job, *, full: bool = False) -> dict:
    out = {"id": job.id, "title": job.title, "company": job.company, "location": job.location, "url": job.url,
           "created_at": job.created_at, "duplicate_of": job.duplicate_of}
    if full:
        out["analysis"] = job.analysis
        out["raw_text"] = job.raw_text
    return out


def file_out(f: GeneratedFile) -> dict:
    return {"id": f.id, "kind": f.kind, "filename": f.filename, "size_bytes": f.size_bytes, "sha256": f.sha256,
            "created_at": f.created_at, "url": f"/api/files/{f.id}"}


def version_out(v: ResumeVersion, *, full: bool = True) -> dict:
    scores = v.scores or {}
    out = {
        "id": v.id, "job_id": v.job_id, "variant": v.variant, "version_no": v.version_no, "parent_id": v.parent_id,
        "status": v.status, "created_at": v.created_at, "approved_at": v.approved_at,
        "profile_revision_id": v.profile_revision_id, "notes": v.notes,
        "summary_scores": {
            "job_fit": (scores.get("job_fit") or {}).get("total"),
            "resume_alignment": (scores.get("resume_alignment") or {}).get("total"),
            "ats_parsing": scores.get("ats_parsing"),
            "evidence_integrity": scores.get("evidence_integrity"),
            "qa": scores.get("qa"),
            "critical_issues": scores.get("critical_issues"),
        },
        "target_title": (v.content.get("header") or {}).get("target_title"),
        "files": [file_out(f) for f in v.files],
    }
    if full:
        out.update(content=v.content, change_log=v.change_log, scores=scores, validation=v.validation)
    return out
