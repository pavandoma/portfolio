"""Master profile lifecycle: import, review/verification, revisions and audit trail.

The master profile is never modified in place. Every change creates a new immutable
revision, and every change is recorded as an audit event with before/after values.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.security import ValidatedUpload, detect_injection
from app.core.taxonomy import get_taxonomy
from app.ingest.claims import analyse_claims, extract_metrics, split_skills
from app.ingest.extract import extract_document
from app.ingest.profile_builder import build_profile, review_issues
from app.ingest.resume_parser import parse_resume
from app.models import AuditEvent, Profile, ProfileRevision, SourceDocument, new_id
from app.schemas.common import stable_id, utcnow
from app.schemas.profile import (
    Achievement,
    CandidateProfile,
    Evidence,
    PhrasingVariant,
    Project,
    Role,
)
from app.services.storage import sha256_bytes, store_upload
from app.tailoring.rewrite import fact_check


class NotFound(LookupError):
    pass


def audit(session: Session, entity_type: str, entity_id: str, action: str, detail: dict | None = None,
          actor: str = "user") -> None:
    session.add(AuditEvent(entity_type=entity_type, entity_id=entity_id, action=action, actor=actor,
                           detail=detail or {}))


def save_document(session: Session, settings: Settings, upload: ValidatedUpload, kind: str, text: str,
                  meta: dict | None = None) -> SourceDocument:
    doc_id = new_id()
    path = store_upload(settings, doc_id, upload.kind, upload.content)
    doc = SourceDocument(id=doc_id, kind=kind, file_type=upload.kind, display_name=upload.display_name,
                         sha256=sha256_bytes(upload.content), size_bytes=len(upload.content), storage_path=str(path),
                         text=text[: settings.max_text_chars], meta=meta or {})
    session.add(doc)
    audit(session, "document", doc_id, "uploaded", {"name": upload.display_name, "kind": kind})
    return doc


def get_profile_row(session: Session) -> Profile | None:
    return session.scalars(select(Profile).order_by(Profile.created_at)).first()


def current(session: Session) -> tuple[Profile, ProfileRevision, CandidateProfile]:
    profile = get_profile_row(session)
    if not profile or not profile.current_revision_id:
        raise NotFound("No master profile yet. Upload your resume first.")
    rev = session.get(ProfileRevision, profile.current_revision_id)
    assert rev is not None
    return profile, rev, CandidateProfile.model_validate(rev.data)


def revision_data(session: Session, revision_id: str) -> CandidateProfile:
    rev = session.get(ProfileRevision, revision_id)
    if not rev:
        raise NotFound("Profile revision not found.")
    return CandidateProfile.model_validate(rev.data)


def _new_revision(session: Session, profile: Profile, data: CandidateProfile, reason: str) -> ProfileRevision:
    last = session.scalars(select(ProfileRevision).where(ProfileRevision.profile_id == profile.id)
                           .order_by(ProfileRevision.revision_no.desc())).first()
    rev = ProfileRevision(profile_id=profile.id, revision_no=(last.revision_no + 1) if last else 1,
                          parent_revision_id=last.id if last else None, reason=reason[:500],
                          data=data.model_dump(mode="json"))
    session.add(rev)
    session.flush()
    profile.current_revision_id = rev.id
    profile.name = data.personal.name
    profile.updated_at = utcnow()
    return rev


def _carry_over(old: CandidateProfile, new: CandidateProfile) -> None:
    """Keep user decisions (verification, corrections, approved wording) across re-imports."""
    old_ach = {a.id: a for a, _ in old.all_achievements()}
    for ach, _ in new.all_achievements():
        prev = old_ach.get(ach.id)
        if prev:
            ach.verification, ach.note, ach.allowed_usage = prev.verification, prev.note, prev.allowed_usage
            ach.text = prev.text
            ach.evidence_ids = prev.evidence_ids
            ach.variants = [v for v in prev.variants if v.origin != "rule_cleanup"] + \
                [v for v in ach.variants if v.origin == "rule_cleanup"]
    for group in ("roles", "projects", "education", "certifications", "skills"):
        old_items = {i.id: i for i in getattr(old, group)}
        for item in getattr(new, group):
            if item.id in old_items:
                item.verification = old_items[item.id].verification
    new.evidence = old.evidence + [e for e in new.evidence if e.id not in {x.id for x in old.evidence}]
    new.work_authorization = old.work_authorization
    old_issue_status = {i.id: (i.status, i.resolution) for i in old.issues}
    for issue in new.issues:
        if issue.id in old_issue_status:
            issue.status, issue.resolution = old_issue_status[issue.id]


def import_resume(session: Session, settings: Settings, upload: ValidatedUpload,
                  today: date | None = None) -> tuple[Profile, ProfileRevision, CandidateProfile, SourceDocument]:
    extracted = extract_document(upload.kind, upload.content)
    if not extracted.text.strip():
        from app.core.security import UploadError

        raise UploadError("No text could be extracted. If this is a scanned image, export a text-based PDF instead.")
    doc = save_document(session, settings, upload, "resume", extracted.text,
                        meta={"pages": extracted.page_count, "fonts": extracted.fonts})
    session.flush()
    parsed = parse_resume(extracted)
    data = build_profile(parsed, document_id=doc.id, document_name=upload.display_name, today=today)
    for warning in detect_injection(extracted.text):
        data.issues.append(_injection_issue(warning))
    profile = get_profile_row(session)
    if profile and profile.current_revision_id:
        old = CandidateProfile.model_validate(session.get(ProfileRevision, profile.current_revision_id).data)
        _carry_over(old, data)
        data.source_document_ids = list(dict.fromkeys(old.source_document_ids + data.source_document_ids))
        reason = f"Re-imported resume {upload.display_name}"
    else:
        profile = Profile(name=data.personal.name)
        session.add(profile)
        session.flush()
        reason = f"Imported resume {upload.display_name}"
    rev = _new_revision(session, profile, data, reason)
    audit(session, "profile", profile.id, "imported", {"revision": rev.revision_no, "document_id": doc.id,
                                                       "parse_warnings": parsed.warnings})
    return profile, rev, data, doc


def _injection_issue(text: str):
    from app.schemas.profile import ProfileIssue

    return ProfileIssue(id=stable_id("iss", "inj", text), kind="injection", message=f"Ignored suspicious text in the "
                        f"document (possible prompt injection): {text[:160]}", severity="warning")


# --------------------------------------------------------------------------- updates

PERSONAL_FIELDS = {"name", "email", "phone", "location"}


def _find_item(data: CandidateProfile, target_id: str):
    for group in ("roles", "projects", "education", "certifications", "skills", "evidence"):
        for item in getattr(data, group):
            if item.id == target_id:
                return group, item
    found = data.find_achievement(target_id)
    if found:
        return "achievement", found[0]
    return None, None


def update_item(session: Session, target_id: str, patch: dict[str, Any], actor: str = "user") -> tuple[ProfileRevision, CandidateProfile]:
    """Apply a reviewed change to one profile item, producing a new revision."""
    profile, _rev, data = current(session)
    group, item = _find_item(data, target_id)
    if item is None:
        raise NotFound(f"No profile item with id {target_id}")
    before = item.model_dump(mode="json")
    allowed: set[str] = {"verification", "note"}
    if group == "achievement":
        allowed |= {"text", "allowed_usage"}
    elif group == "roles":
        allowed |= {"title", "organization", "location", "start", "end", "employment_type"}
    elif group == "projects":
        allowed |= {"name", "context", "repo_url", "url", "subtitle"}
    elif group == "education":
        allowed |= {"degree", "institution", "status", "gpa", "location", "end"}
    elif group == "certifications":
        allowed |= {"name", "detail", "issuer", "date", "credential_url"}
    elif group == "skills":
        allowed |= {"display"}
    unknown = set(patch) - allowed
    if unknown:
        raise ValueError(f"Fields not editable here: {', '.join(sorted(unknown))}")
    for key, value in patch.items():
        setattr(item, key, value)
    if group == "achievement":
        ach: Achievement = item  # type: ignore[assignment]
        if "text" in patch and patch["text"] != ach.original_text:
            # A user correction becomes the canonical wording; the original stays as the source record.
            ach.verification = patch.get("verification", "user_corrected")
            _, parent = data.find_achievement(ach.id)  # type: ignore[misc]
            kind = "project" if isinstance(parent, Project) else "role"
            ctx = parent.context if isinstance(parent, Project) else None
            ach.technologies, ach.competencies = split_skills(ach.text)
            ach.metrics = extract_metrics(ach.text)
            ach.flags = analyse_claims(ach.text, parent_kind=kind, parent_context=ctx)
            ach.variants = [v for v in ach.variants if v.origin == "user"]
        ach.last_modified = utcnow()
        ach.evidence_strength = _strength(ach)
    _refresh_issues(data)
    rev = _new_revision(session, profile, data, f"Updated {group} {target_id}")
    audit(session, "profile_item", target_id, "updated",
          {"group": group, "before": before, "after": item.model_dump(mode="json"), "revision": rev.revision_no},
          actor=actor)
    return rev, data


def _strength(ach: Achievement) -> str:
    if ach.verification == "rejected":
        return "none"
    if ach.verification in ("verified", "user_corrected") and ach.evidence_ids:
        return "strong"
    if ach.verification in ("verified", "user_corrected") or ach.evidence_ids:
        return "moderate"
    return "weak"


def _refresh_issues(data: CandidateProfile) -> None:
    status = {i.id: (i.status, i.resolution) for i in data.issues}
    extra = [i for i in data.issues if i.kind == "injection"]
    fresh = review_issues(data)
    for issue in fresh:
        target_verified = False
        if issue.target_id:
            _, item = _find_item(data, issue.target_id)
            target_verified = getattr(item, "verification", None) in ("verified", "user_corrected", "rejected")
        if issue.id in status:
            issue.status, issue.resolution = status[issue.id]
        if target_verified and issue.kind in ("needs_verification", "unsupported_claim") and issue.status == "open":
            issue.status, issue.resolution = "resolved", "Reviewed by user"
    data.issues = fresh + extra


def update_personal(session: Session, patch: dict[str, Any]) -> tuple[ProfileRevision, CandidateProfile]:
    profile, _rev, data = current(session)
    before = data.personal.model_dump(mode="json")
    for key, value in patch.items():
        if key in PERSONAL_FIELDS:
            setattr(data.personal, key, value or None if key != "name" else value)
        elif key == "links":
            from app.schemas.profile import Link

            data.personal.links = [Link.model_validate(x) for x in value]
        else:
            raise ValueError(f"Unknown personal field {key}")
    data.personal.verification = "verified"
    _refresh_issues(data)
    rev = _new_revision(session, profile, data, "Updated personal information")
    audit(session, "profile", profile.id, "personal_updated", {"before": before, "after": data.personal.model_dump(mode="json")})
    return rev, data


def update_work_authorization(session: Session, patch: dict[str, Any]) -> tuple[ProfileRevision, CandidateProfile]:
    profile, _rev, data = current(session)
    before = data.work_authorization.model_dump(mode="json")
    data.work_authorization = data.work_authorization.model_copy(update=patch)
    data.work_authorization = type(data.work_authorization).model_validate(data.work_authorization.model_dump())
    _refresh_issues(data)
    rev = _new_revision(session, profile, data, "Updated work authorization")
    audit(session, "profile", profile.id, "work_authorization_updated",
          {"before": before, "after": data.work_authorization.model_dump(mode="json")})
    return rev, data


def set_issue_status(session: Session, issue_id: str, status: str, resolution: str | None = None):
    profile, _rev, data = current(session)
    issue = next((i for i in data.issues if i.id == issue_id), None)
    if not issue:
        raise NotFound("Issue not found")
    issue.status, issue.resolution = status, resolution  # type: ignore[assignment]
    rev = _new_revision(session, profile, data, f"Issue {issue_id} -> {status}")
    audit(session, "profile_issue", issue_id, status, {"resolution": resolution})
    return rev, data


def add_variant(session: Session, achievement_id: str, text: str, origin: str = "user", approved: bool = True,
                emphasis: list[str] | None = None) -> tuple[ProfileRevision, CandidateProfile, PhrasingVariant]:
    """Add alternative wording. It must pass the fact-preservation check against the source."""
    profile, _rev, data = current(session)
    found = data.find_achievement(achievement_id)
    if not found:
        raise NotFound("Achievement not found")
    ach, parent = found
    academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
    fc = fact_check(text, [ach.text, ach.original_text], academic=academic)
    variant = PhrasingVariant(id=stable_id("var", ach.id, text), text=text, origin=origin, approved=approved and fc.passed,  # type: ignore[arg-type]
                              fact_check=fc, emphasis=emphasis or [])
    ach.variants = [v for v in ach.variants if v.id != variant.id] + [variant]
    rev = _new_revision(session, profile, data, f"Added wording for {achievement_id}")
    audit(session, "achievement", achievement_id, "variant_added",
          {"variant_id": variant.id, "origin": origin, "fact_check": fc.model_dump()})
    return rev, data, variant


def set_variant_approval(session: Session, achievement_id: str, variant_id: str, approved: bool):
    profile, _rev, data = current(session)
    found = data.find_achievement(achievement_id)
    if not found:
        raise NotFound("Achievement not found")
    ach, _ = found
    v = next((v for v in ach.variants if v.id == variant_id), None)
    if not v:
        raise NotFound("Wording variant not found")
    if approved and v.fact_check and not v.fact_check.passed:
        raise ValueError("This wording failed the fact check and cannot be approved: " + "; ".join(v.fact_check.problems))
    v.approved = approved
    rev = _new_revision(session, profile, data, f"{'Approved' if approved else 'Unapproved'} wording {variant_id}")
    audit(session, "achievement", achievement_id, "variant_approval", {"variant_id": variant_id, "approved": approved})
    return rev, data


def add_issues(session: Session, issues: list, reason: str) -> tuple[ProfileRevision, CandidateProfile]:
    profile, _rev, data = current(session)
    known = {i.id for i in data.issues}
    data.issues.extend(i for i in issues if i.id not in known)
    rev = _new_revision(session, profile, data, reason)
    audit(session, "profile", profile.id, "issues_added", {"count": len(issues), "reason": reason})
    return rev, data


def add_evidence(session: Session, evidence: Evidence) -> tuple[ProfileRevision, CandidateProfile]:
    profile, _rev, data = current(session)
    data.evidence = [e for e in data.evidence if e.id != evidence.id] + [evidence]
    for target in evidence.linked_ids:
        found = data.find_achievement(target)
        if found and evidence.id not in found[0].evidence_ids:
            found[0].evidence_ids.append(evidence.id)
            found[0].evidence_strength = _strength(found[0])
    rev = _new_revision(session, profile, data, f"Added evidence {evidence.title}")
    audit(session, "evidence", evidence.id, "added", {"title": evidence.title, "uri": evidence.uri,
                                                      "linked": evidence.linked_ids})
    return rev, data


def add_achievement(session: Session, parent_id: str, text: str) -> tuple[ProfileRevision, CandidateProfile, Achievement]:
    """User-authored achievement (e.g. to document a skill that was only listed)."""
    from app.schemas.common import SourceRef

    profile, _rev, data = current(session)
    parent = next((p for p in [*data.roles, *data.projects] if p.id == parent_id), None)
    if parent is None:
        raise NotFound("Role or project not found")
    kind = "project" if isinstance(parent, Project) else "role"
    ctx = parent.context if isinstance(parent, Project) else None
    techs, comps = split_skills(text)
    ach = Achievement(id=stable_id("ach", parent_id, text), text=text, original_text=text,
                      source_ref=SourceRef(document_name="Entered by user", section=kind, original_text=text),
                      verification="verified", technologies=techs, competencies=comps,
                      metrics=extract_metrics(text), flags=analyse_claims(text, parent_kind=kind, parent_context=ctx))
    ach.evidence_strength = _strength(ach)
    parent.achievements.append(ach)
    tax = get_taxonomy()
    expanded = set(techs + comps)
    for t in list(expanded):
        expanded |= set(tax.ancestors(t))
    for skill in data.skills:
        if skill.name in expanded and ach.id not in skill.evidence_achievement_ids:
            skill.evidence_achievement_ids.append(ach.id)
            skill.self_reported_only = False
    _refresh_issues(data)
    rev = _new_revision(session, profile, data, f"Added achievement to {parent_id}")
    audit(session, "achievement", ach.id, "created", {"parent": parent_id, "text": text})
    return rev, data, ach


def list_revisions(session: Session) -> list[ProfileRevision]:
    profile = get_profile_row(session)
    if not profile:
        return []
    return list(session.scalars(select(ProfileRevision).where(ProfileRevision.profile_id == profile.id)
                                .order_by(ProfileRevision.revision_no.desc())))


def list_audit(session: Session, limit: int = 200) -> list[AuditEvent]:
    return list(session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)))


def completeness(data: CandidateProfile) -> dict[str, Any]:
    checks = {
        "name": bool(data.personal.name), "email": bool(data.personal.email), "phone": bool(data.personal.phone),
        "location": bool(data.personal.location), "linkedin": any(lk.label == "LinkedIn" for lk in data.personal.links),
        "experience": bool(data.roles), "projects": bool(data.projects), "education": bool(data.education),
        "skills": len(data.skills) >= 5, "work_authorization": data.work_authorization.status != "unknown",
    }
    achievements = [a for a, _ in data.all_achievements()]
    reviewed = [a for a in achievements if a.verification != "unverified"]
    return {
        "score": round(100 * sum(checks.values()) / len(checks)),
        "checks": checks,
        "achievements_total": len(achievements),
        "achievements_reviewed": len(reviewed),
        "open_issues": sum(1 for i in data.issues if i.status == "open"),
        "critical_issues": sum(1 for i in data.issues if i.status == "open" and i.severity == "critical"),
    }


def roles_and_projects(data: CandidateProfile) -> list[Role | Project]:
    return [*data.roles, *data.projects]


# --------------------------------------------------------------------------- suggestion packs

def _norm(text: str) -> str:
    import re as _re

    return _re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def apply_pack_to_profile(data: CandidateProfile, pack: dict) -> list[dict]:
    """Attach wording variants from a suggestion pack. Every variant is fact-checked; failures are
    kept (so the user can see why) but can never be approved or used."""
    results = []
    origin = pack.get("origin", "assistant")
    for sug in pack.get("suggestions", []):
        key = _norm(sug["match"])
        match = next(((a, p) for a, p in data.all_achievements() if _norm(a.original_text).startswith(key)), None)
        if not match:
            results.append({"match": sug["match"], "status": "no_matching_achievement"})
            continue
        ach, parent = match
        academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
        for v in sug.get("variants", []):
            fc = fact_check(v["text"], [ach.text, ach.original_text], academic=academic)
            variant = PhrasingVariant(id=stable_id("var", ach.id, v["text"]), text=v["text"], origin=origin,
                                      approved=False, fact_check=fc, emphasis=list(v.get("emphasis", [])))
            ach.variants = [x for x in ach.variants if x.id != variant.id] + [variant]
            results.append({"achievement_id": ach.id, "variant_id": variant.id, "passed": fc.passed,
                            "problems": fc.problems})
    return results


def apply_suggestion_pack(session: Session, pack: dict) -> tuple[ProfileRevision, CandidateProfile, list[dict]]:
    profile, _rev, data = current(session)
    results = apply_pack_to_profile(data, pack)
    rev = _new_revision(session, profile, data, f"Added wording suggestions ({pack.get('origin', 'assistant')})")
    audit(session, "profile", profile.id, "suggestions_added",
          {"origin": pack.get("origin"), "count": len(results),
           "failed": [r for r in results if r.get("passed") is False]})
    return rev, data, results
