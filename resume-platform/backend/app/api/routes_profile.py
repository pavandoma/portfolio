"""Master profile: import, review, verification, evidence and suggestions."""

from __future__ import annotations

from typing import Any, Literal

import yaml
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import validate_upload
from app.db import get_session
from app.ingest.extract import extract_document
from app.ingest.github import best_project_match, fetch_repo
from app.ingest.resume_parser import parse_resume
from app.llm.base import LLMNotConfigured
from app.llm.factory import get_provider
from app.llm.tasks import suggest_wording
from app.models import ProfileRevision
from app.schemas.common import stable_id
from app.schemas.profile import Evidence, ProfileIssue
from app.services import profiles

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _out(rev: ProfileRevision, data) -> dict:
    return {"revision": {"id": rev.id, "number": rev.revision_no, "reason": rev.reason, "created_at": rev.created_at},
            "profile": data.model_dump(mode="json"), "completeness": profiles.completeness(data)}


async def _read_upload(file: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        from app.core.security import UploadError

        raise UploadError(f"File is larger than the {limit // (1024 * 1024)} MB limit.")
    return content


@router.post("/import")
async def import_resume(file: UploadFile = File(...), session: Session = Depends(get_session)):
    settings = get_settings()
    upload = validate_upload(file.filename or "resume", await _read_upload(file), settings)
    _profile, rev, data, doc = profiles.import_resume(session, settings, upload)
    return {**_out(rev, data), "document_id": doc.id}


@router.get("")
def get_profile(session: Session = Depends(get_session)):
    _p, rev, data = profiles.current(session)
    return _out(rev, data)


@router.get("/revisions")
def revisions(session: Session = Depends(get_session)):
    return [{"id": r.id, "number": r.revision_no, "reason": r.reason, "created_at": r.created_at}
            for r in profiles.list_revisions(session)]


@router.get("/revisions/{revision_id}")
def revision(revision_id: str, session: Session = Depends(get_session)):
    rev = session.get(ProfileRevision, revision_id)
    if not rev:
        raise profiles.NotFound("Revision not found")
    return {"id": rev.id, "number": rev.revision_no, "reason": rev.reason, "profile": rev.data}


class ItemPatch(BaseModel):
    patch: dict[str, Any]


@router.patch("/items/{item_id}")
def patch_item(item_id: str, body: ItemPatch, session: Session = Depends(get_session)):
    rev, data = profiles.update_item(session, item_id, body.patch)
    return _out(rev, data)


class PersonalPatch(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[dict] | None = None


@router.patch("/personal")
def patch_personal(body: PersonalPatch, session: Session = Depends(get_session)):
    rev, data = profiles.update_personal(session, body.model_dump(exclude_none=True))
    return _out(rev, data)


class WorkAuthPatch(BaseModel):
    status: Literal["unknown", "citizen", "permanent_resident", "authorized_no_sponsorship",
                    "authorized_requires_future_sponsorship", "requires_sponsorship"] | None = None
    note: str | None = None
    has_security_clearance: bool | None = None


@router.patch("/work-authorization")
def patch_work_auth(body: WorkAuthPatch, session: Session = Depends(get_session)):
    rev, data = profiles.update_work_authorization(session, body.model_dump(exclude_none=True))
    return _out(rev, data)


class VariantIn(BaseModel):
    text: str = Field(min_length=10, max_length=600)
    emphasis: list[str] = Field(default_factory=list)


@router.post("/achievements/{achievement_id}/variants")
def add_variant(achievement_id: str, body: VariantIn, session: Session = Depends(get_session)):
    rev, data, variant = profiles.add_variant(session, achievement_id, body.text, origin="user", approved=True,
                                              emphasis=body.emphasis)
    return {**_out(rev, data), "variant": variant.model_dump(mode="json")}


class ApprovalIn(BaseModel):
    approved: bool


@router.post("/achievements/{achievement_id}/variants/{variant_id}/approval")
def approve_variant(achievement_id: str, variant_id: str, body: ApprovalIn, session: Session = Depends(get_session)):
    rev, data = profiles.set_variant_approval(session, achievement_id, variant_id, body.approved)
    return _out(rev, data)


@router.post("/achievements/{achievement_id}/suggest")
def suggest(achievement_id: str, session: Session = Depends(get_session)):
    """LLM wording suggestions (optional feature). Every suggestion is fact-checked; failures are reported."""
    provider = get_provider()
    if provider is None:
        raise LLMNotConfigured("LLM features are off (LLM_PROVIDER=none). Add wording manually or configure a provider.")
    _p, _rev, data = profiles.current(session)
    found = data.find_achievement(achievement_id)
    if not found:
        raise profiles.NotFound("Achievement not found")
    ach, parent = found
    kept, rejected = suggest_wording(provider, ach, parent, ach.technologies[:4])
    pack = {"origin": "llm", "suggestions": [{"match": ach.original_text[:60],
                                              "variants": [{"text": v.text, "emphasis": v.emphasis} for v in kept]}]}
    rev, data, _results = profiles.apply_suggestion_pack(session, pack)
    return {**_out(rev, data), "kept": len(kept), "rejected": rejected}


class AchievementIn(BaseModel):
    parent_id: str
    text: str = Field(min_length=10, max_length=600)


@router.post("/achievements")
def add_achievement(body: AchievementIn, session: Session = Depends(get_session)):
    rev, data, ach = profiles.add_achievement(session, body.parent_id, body.text)
    return {**_out(rev, data), "achievement_id": ach.id}


class IssueIn(BaseModel):
    status: Literal["open", "resolved", "dismissed"]
    resolution: str | None = None


@router.post("/issues/{issue_id}")
def set_issue(issue_id: str, body: IssueIn, session: Session = Depends(get_session)):
    rev, data = profiles.set_issue_status(session, issue_id, body.status, body.resolution)
    return _out(rev, data)


@router.post("/suggestion-pack")
async def suggestion_pack(file: UploadFile = File(...), session: Session = Depends(get_session)):
    raw = await _read_upload(file)
    pack = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(pack, dict) or "suggestions" not in pack:
        raise ValueError("Not a suggestion pack (expected a 'suggestions' list).")
    pack["origin"] = pack.get("origin") if pack.get("origin") in ("assistant", "llm", "user") else "assistant"
    rev, data, results = profiles.apply_suggestion_pack(session, pack)
    return {**_out(rev, data), "results": results}


class GitHubIn(BaseModel):
    url: str
    project_id: str | None = None


@router.post("/evidence/github")
def github_evidence(body: GitHubIn, session: Session = Depends(get_session)):
    ev = fetch_repo(body.url, get_settings())
    _p, _rev, data = profiles.current(session)
    project = next((p for p in data.projects if p.id == body.project_id), None) if body.project_id else None
    score = None
    if project is None:
        project, score = best_project_match(ev, data.projects)
    linked = [a.id for a in project.achievements] if project else []
    evidence = Evidence(id=stable_id("ev", ev.url), kind="repository", title=f"{ev.owner}/{ev.repo}", uri=ev.url,
                        description=(ev.description or ev.readme_excerpt[:300]).strip(), technologies=ev.technologies,
                        linked_ids=linked)
    rev, data = profiles.add_evidence(session, evidence)
    if project and not project.repo_url:
        rev, data = profiles.update_item(session, project.id, {"repo_url": ev.url})
    return {**_out(rev, data), "repository": {"technologies": ev.technologies, "languages": ev.languages,
                                              "linked_project": project.name if project else None,
                                              "match_score": score}}


class EvidenceIn(BaseModel):
    kind: Literal["document", "link", "note", "certificate"]
    title: str = Field(min_length=2, max_length=200)
    uri: str | None = None
    description: str = ""
    linked_ids: list[str] = Field(default_factory=list)


@router.post("/evidence")
def add_evidence(body: EvidenceIn, session: Session = Depends(get_session)):
    ev = Evidence(id=stable_id("ev", body.title, body.uri or "", body.description), **body.model_dump())
    rev, data = profiles.add_evidence(session, ev)
    return _out(rev, data)


@router.post("/documents")
async def supporting_document(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Upload a supporting document (another resume version, LinkedIn export, transcript). It becomes evidence, and
    differences in contact details or job titles are raised as conflicts for you to resolve."""
    settings = get_settings()
    upload = validate_upload(file.filename or "document", await _read_upload(file), settings)
    extracted = extract_document(upload.kind, upload.content)
    doc = profiles.save_document(session, settings, upload, "supporting", extracted.text)
    session.flush()
    parsed = parse_resume(extracted)
    _p, _rev, data = profiles.current(session)
    conflicts = []
    for field_name, theirs in (("email", parsed.emails[0] if parsed.emails else None),
                               ("phone", parsed.phones[0] if parsed.phones else None)):
        mine = getattr(data.personal, field_name)
        if theirs and mine and "".join(filter(str.isalnum, theirs.lower())) != "".join(filter(str.isalnum, mine.lower())):
            conflicts.append(ProfileIssue(id=stable_id("iss", "conflict", field_name, theirs), kind="conflict",
                                          field=f"personal.{field_name}", severity="warning",
                                          message=f"{upload.display_name} lists {field_name} '{theirs}' but the master "
                                                  f"profile has '{mine}'. Which is current?", options=[mine, theirs]))
    for e in parsed.experience:
        for r in data.roles:
            if r.organization.lower() == e.organization.lower() and e.title and e.title.lower() != r.title.lower():
                conflicts.append(ProfileIssue(id=stable_id("iss", "conflict", r.id, e.title), kind="conflict",
                                              target_id=r.id, field="title", severity="warning",
                                              message=f"{upload.display_name} gives the title '{e.title}' at "
                                                      f"{r.organization}; the master profile says '{r.title}'. "
                                                      "Confirm your official title.", options=[r.title, e.title]))
    ev = Evidence(id=stable_id("ev", doc.id), kind="document", title=upload.display_name, source_document_id=doc.id,
                  description=f"Supporting document ({upload.kind}, {len(extracted.text)} characters)")
    rev, data = profiles.add_evidence(session, ev)
    if conflicts:
        rev, data = profiles.add_issues(session, conflicts, f"Conflicts from {upload.display_name}")
    return {**_out(rev, data), "conflicts": [c.model_dump() for c in conflicts]}


@router.get("/suggest-pack-template")
def pack_template():
    return {"candidate": "Your Name", "origin": "user", "suggestions": [
        {"match": "First words of the original bullet", "variants": [{"text": "Your improved wording.",
                                                                       "emphasis": ["SQL"]}]}]}

