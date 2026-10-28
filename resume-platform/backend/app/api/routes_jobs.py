"""Job analysis: paste text, upload a file or give a URL; match against the master profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import job_out
from app.config import get_settings
from app.core.security import validate_upload
from app.db import get_session, session_scope
from app.ingest.extract import extract_document
from app.ingest.url_fetch import fetch_job
from app.llm.base import LLMNotConfigured
from app.llm.factory import get_provider
from app.llm.tasks import refine_job_categories
from app.models import Job, MatchRecord
from app.schemas.match import MatchReport, Weights
from app.services import jobs as job_service
from app.services import profiles, tasks
from app.services.applications import overview, upsert

router = APIRouter(prefix="/api", tags=["jobs"])


class JobIn(BaseModel):
    text: str | None = Field(default=None, max_length=100_000)
    url: str | None = Field(default=None, max_length=2048)
    title: str | None = Field(default=None, max_length=300)
    company: str | None = Field(default=None, max_length=300)
    allow_duplicate: bool = False
    fetch_with: str = "auto"  # auto | builtin | firecrawl

    @model_validator(mode="after")
    def need_text_or_url(self):
        if not (self.text and self.text.strip()) and not self.url:
            raise ValueError("Paste the job description or give a URL.")
        return self


def _create(session: Session, body: JobIn) -> dict:
    text = body.text or ""
    notes: list[str] = []
    title, company = body.title, body.company
    if not text.strip() and body.url:
        fetched = fetch_job(body.url, get_settings(), prefer=body.fetch_with)
        text = fetched.text
        title = title or fetched.title
        company = company or fetched.company
        notes = fetched.notes + [f"Fetched with {fetched.method}"]
    if len(text.strip()) < 80:
        raise ValueError("The job description is too short to analyse. Paste the full text.")
    job, duplicate = job_service.create_job(session, text, url=body.url, title=title, company=company,
                                            allow_duplicate=body.allow_duplicate)
    return {**job_out(job, full=True), "duplicate": duplicate, "notes": notes}


@router.post("/jobs")
def create_job(body: JobIn, session: Session = Depends(get_session)):
    return _create(session, body)


@router.post("/jobs/async")
def create_job_async(body: JobIn):
    def run():
        with session_scope() as s:
            out = _create(s, body)
            return {"job_id": out["id"], "duplicate": out["duplicate"]}

    return {"task_id": tasks.submit("job_import", run)}


@router.post("/jobs/upload")
async def upload_job(file: UploadFile = File(...), title: str | None = Form(None), company: str | None = Form(None),
                     url: str | None = Form(None), session: Session = Depends(get_session)):
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    upload = validate_upload(file.filename or "job", content, settings)
    text = extract_document(upload.kind, upload.content).text
    doc = profiles.save_document(session, settings, upload, "job", text)
    session.flush()
    job, duplicate = job_service.create_job(session, text, url=url, title=title, company=company,
                                            source_document_id=doc.id)
    return {**job_out(job, full=True), "duplicate": duplicate}


@router.get("/jobs")
def list_jobs(session: Session = Depends(get_session)):
    return [job_out(j) for j in session.scalars(select(Job).order_by(Job.created_at.desc()))]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, session: Session = Depends(get_session)):
    return job_out(job_service.get_job(session, job_id), full=True)


class JobPatch(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None


@router.patch("/jobs/{job_id}")
def patch_job(job_id: str, body: JobPatch, session: Session = Depends(get_session)):
    job = job_service.update_job_fields(session, job_id, title=body.title, company=body.company, location=body.location)
    return job_out(job, full=True)


@router.post("/jobs/{job_id}/refine")
def refine_job(job_id: str, session: Session = Depends(get_session)):
    """Optional LLM pass over requirements whose category was only inferred (anchored to exact quotes)."""
    provider = get_provider()
    if provider is None:
        raise LLMNotConfigured("LLM features are off (LLM_PROVIDER=none).")
    job = job_service.get_job(session, job_id)
    updated, changed = refine_job_categories(provider, job_service.job_analysis(job), job.raw_text)
    job.analysis = updated.model_dump(mode="json")
    return {**job_out(job, full=True), "changed": changed}


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, session: Session = Depends(get_session)):
    from app.services.resumes import delete_version, list_versions

    settings = get_settings()
    for v in list_versions(session, job_id):
        delete_version(session, settings, v.id)
    session.delete(job_service.get_job(session, job_id))
    profiles.audit(session, "job", job_id, "deleted")
    return {"deleted": True}


@router.post("/jobs/{job_id}/match")
def match(job_id: str, weights: Weights | None = None, session: Session = Depends(get_session)):
    rec, report = job_service.run_match(session, job_id, weights)
    return {"match_id": rec.id, "report": report.model_dump(mode="json")}


@router.get("/jobs/{job_id}/match")
def latest_match(job_id: str, session: Session = Depends(get_session)):
    rec = job_service.latest_match(session, job_id)
    if not rec:
        rec, report = job_service.run_match(session, job_id)
        return {"match_id": rec.id, "report": report.model_dump(mode="json")}
    return {"match_id": rec.id, "report": MatchReport.model_validate(rec.report).model_dump(mode="json")}


@router.get("/jobs/{job_id}/matches")
def match_history(job_id: str, session: Session = Depends(get_session)):
    rows = session.scalars(select(MatchRecord).where(MatchRecord.job_id == job_id).order_by(MatchRecord.created_at.desc()))
    return [{"id": r.id, "job_fit": r.job_fit, "profile_revision_id": r.profile_revision_id, "input_hash": r.input_hash,
             "created_at": r.created_at} for r in rows]


# --------------------------------------------------------------------------- applications


@router.get("/applications")
def applications(session: Session = Depends(get_session)):
    return overview(session)


class ApplicationIn(BaseModel):
    status: str | None = None
    resume_version_id: str | None = None
    notes: str | None = None


@router.put("/applications/{job_id}")
def update_application(job_id: str, body: ApplicationIn, session: Session = Depends(get_session)):
    app = upsert(session, job_id, status=body.status, resume_version_id=body.resume_version_id, notes=body.notes)
    return {"id": app.id, "job_id": app.job_id, "status": app.status, "resume_version_id": app.resume_version_id,
            "notes": app.notes, "applied_at": app.applied_at}
