"""Resume generation, editor operations, approval, previews and downloads."""

from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.serializers import version_out
from app.config import get_settings
from app.db import get_session, session_scope
from app.models import GeneratedFile
from app.schemas.match import Weights
from app.services import resumes, tasks
from app.services.profiles import NotFound
from app.services.storage import resolve_stored
from app.tailoring.tailor import TailorOptions

router = APIRouter(prefix="/api", tags=["resumes"])
MEDIA = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         ".json": "application/json", ".md": "text/markdown; charset=utf-8"}


class GenerateIn(BaseModel):
    job_id: str | None = None
    variant: str | None = None
    page_target: int | None = Field(default=None, ge=1, le=3)
    use_unapproved_wording: bool = True
    font_family: str | None = Field(default=None, pattern="^(sans|serif)$")
    max_cycles: int | None = Field(default=None, ge=1, le=3)
    weights: Weights | None = None
    notes: str = ""

    @model_validator(mode="after")
    def target(self):
        if bool(self.job_id) == bool(self.variant):
            raise ValueError("Give exactly one of job_id or variant.")
        return self


def _generate(session: Session, body: GenerateIn):
    options = TailorOptions(page_target=body.page_target, use_unapproved_wording=body.use_unapproved_wording,
                            font_family=body.font_family)
    return resumes.generate(session, get_settings(), job_id=body.job_id, variant=body.variant, options=options,
                            weights=body.weights, max_cycles=body.max_cycles, notes=body.notes)


@router.post("/resumes")
def generate(body: GenerateIn, session: Session = Depends(get_session)):
    return version_out(_generate(session, body))


@router.post("/resumes/async")
def generate_async(body: GenerateIn):
    def run():
        with session_scope() as s:
            v = _generate(s, body)
            return {"resume_version_id": v.id}

    return {"task_id": tasks.submit("resume_generation", run)}


@router.get("/resumes")
def list_resumes(job_id: str | None = None, session: Session = Depends(get_session)):
    return [version_out(v, full=False) for v in resumes.list_versions(session, job_id)]


@router.get("/resumes/{version_id}")
def get_resume(version_id: str, session: Session = Depends(get_session)):
    return version_out(resumes.get_version(session, version_id))


@router.get("/resumes/{version_id}/comparison")
def comparison(version_id: str, session: Session = Depends(get_session)):
    return resumes.comparison(session, resumes.get_version(session, version_id))


@router.get("/resumes/{version_id}/revisions")
def revisions(version_id: str, session: Session = Depends(get_session)):
    v = resumes.get_version(session, version_id)
    return [{"iteration": r.iteration, "scores": r.scores, "diagnoses": r.diagnoses, "actions": r.actions,
             "content": r.content} for r in v.revisions]


class EditIn(BaseModel):
    ops: list[dict] = Field(min_length=1, max_length=50)


@router.post("/resumes/{version_id}/edits")
def edit(version_id: str, body: EditIn, session: Session = Depends(get_session)):
    return version_out(resumes.edit(session, get_settings(), version_id, body.ops))


@router.post("/resumes/{version_id}/approve")
def approve(version_id: str, session: Session = Depends(get_session)):
    return version_out(resumes.approve(session, version_id))


@router.delete("/resumes/{version_id}")
def delete(version_id: str, session: Session = Depends(get_session)):
    resumes.delete_version(session, get_settings(), version_id)
    return {"deleted": True}


@router.get("/resumes/{version_id}/preview.png")
def preview(version_id: str, page: int = Query(1, ge=1, le=5), dpi: int = Query(110, ge=50, le=200),
            session: Session = Depends(get_session)):
    """Image of the actual rendered PDF page (for browsers that cannot display PDFs inline)."""
    import pymupdf

    v = resumes.get_version(session, version_id)
    pdf_file = next((f for f in v.files if f.kind == "pdf"), None)
    data = resolve_stored(get_settings(), pdf_file.path).read_bytes() if pdf_file else resumes.regenerate_pdf_preview(v)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if page > doc.page_count:
            raise NotFound("Page out of range")
        png = doc[page - 1].get_pixmap(dpi=dpi).tobytes("png")
    return Response(content=png, media_type="image/png")


@router.get("/resumes/{version_id}/export.zip")
def export_zip(version_id: str, session: Session = Depends(get_session)):
    v = resumes.get_version(session, version_id)
    settings = get_settings()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in v.files:
            zf.write(resolve_stored(settings, f.path), arcname=f.filename)
    name = f"resume_v{v.version_no}_{version_id[:8]}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/files/{file_id}")
def download(file_id: str, inline: bool = False, session: Session = Depends(get_session)):
    f = session.get(GeneratedFile, file_id)
    if not f:
        raise NotFound("File not found")
    path = resolve_stored(get_settings(), f.path)
    ext = "." + f.filename.rsplit(".", 1)[-1]
    return FileResponse(path, media_type=MEDIA.get(ext, "application/octet-stream"), filename=f.filename,
                        content_disposition_type="inline" if inline else "attachment")
