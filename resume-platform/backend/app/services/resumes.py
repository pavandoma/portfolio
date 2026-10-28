"""Resume versions: generation, editing, approval, exports and history.

Every generated or edited resume is a new immutable version pinned to the profile revision it
was built from, so the exact document sent to an employer can always be recovered.
"""

from __future__ import annotations

import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.matching.engine import score_profile
from app.models import GeneratedFile, Job, ResumeRevision, ResumeVersion, SourceDocument
from app.optimize.loop import evaluate, optimize
from app.render import reports
from app.render.docx_writer import render_docx
from app.render.pdf_writer import render_pdf
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ScoreCard, Weights
from app.schemas.profile import CandidateProfile
from app.schemas.resume import ChangeLogEntry, ResumeBullet, TailoredResume
from app.schemas.validation import ExternalValidatorResult, ValidationBundle
from app.services import jobs as job_service
from app.services import profiles
from app.services.profiles import NotFound, audit
from app.services.storage import delete_stored, output_dir, sha256_bytes, store_output
from app.tailoring.diff import bullet_diffs, original_plain_text, resume_plain_text
from app.tailoring.presets import PRESETS, preset_job
from app.tailoring.tailor import TailorOptions
from app.validation.adapters.base import ValidationContext
from app.validation.adapters.registry import run_all


def _source_fonts(session: Session, data: CandidateProfile) -> list[str]:
    for doc_id in data.source_document_ids:
        doc = session.get(SourceDocument, doc_id)
        if doc and doc.meta.get("fonts"):
            return list(doc.meta["fonts"])
    return []


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:40] or "resume"


def _job_context(session: Session, job_id: str | None, variant: str | None,
                 weights: Weights | None, today: date | None) -> tuple[Job | None, JobAnalysis, MatchReport, str]:
    _p, _rev, data = profiles.current(session)
    if job_id:
        job = job_service.get_job(session, job_id)
        analysis = job_service.job_analysis(job)
        _rec, report = job_service.run_match(session, job_id, weights, today)
        return job, analysis, report, job.raw_text
    if variant:
        if variant not in PRESETS:
            raise NotFound(f"Unknown variant {variant}")
        analysis = preset_job(variant)
        return None, analysis, score_profile(data, analysis, weights, today=today), ""
    raise ValueError("Provide a job_id or a variant.")


def generate(session: Session, settings: Settings, *, job_id: str | None = None, variant: str | None = None,
             options: TailorOptions | None = None, weights: Weights | None = None,
             max_cycles: int | None = None, notes: str = "") -> ResumeVersion:
    options = options or TailorOptions()
    _profile_row, rev, data = profiles.current(session)
    job, analysis, report, job_text = _job_context(session, job_id, variant, weights, options.today)
    result = optimize(data, analysis, report, options, weights=weights,
                      max_cycles=max_cycles or settings.max_revision_cycles,
                      source_fonts=_source_fonts(session, data), variant=variant)
    final = result.final
    ctx = ValidationContext(resume=final.resume, resume_text=resume_plain_text(final.resume), pdf=final.pdf,
                            docx=final.docx, job=analysis, job_text=job_text)
    external = run_all(ctx)
    previous = session.scalars(select(ResumeVersion).where(
        ResumeVersion.job_id == job_id if job_id else ResumeVersion.variant == variant)
        .order_by(ResumeVersion.version_no.desc())).first()
    iterations = [{"iteration": it.number, "scores": it.scores(), "actions": it.actions,
                   "diagnoses": [d.__dict__ for d in it.diagnoses]} for it in result.iterations]
    version = ResumeVersion(
        job_id=job_id, profile_revision_id=rev.id, version_no=(previous.version_no + 1) if previous else 1,
        parent_id=previous.id if previous else None, variant=variant, status="draft",
        content=final.resume.model_dump(mode="json"),
        change_log=[c.model_dump(mode="json") for c in result.change_log],
        scores=_scores(report, final.alignment, final.ats, final.integrity, final.qa, final.critical, iterations,
                       result.stop_reason),
        validation=ValidationBundle(ats=final.ats, integrity=final.integrity, qa=final.qa,
                                    external=external).model_dump(mode="json"),
        notes=notes,
    )
    session.add(version)
    session.flush()
    for it in result.iterations:
        session.add(ResumeRevision(resume_version_id=version.id, iteration=it.number,
                                   content=it.resume.model_dump(mode="json"), scores=it.scores(),
                                   diagnoses=[d.__dict__ for d in it.diagnoses], actions=it.actions))
    _write_files(session, settings, version, data, final.resume, final.pdf, final.docx, report, final.alignment,
                 result.change_log, iterations, external)
    audit(session, "resume", version.id, "generated", {"job_id": job_id, "variant": variant,
                                                      "version_no": version.version_no, "stop": result.stop_reason})
    return version


def _scores(report: MatchReport, alignment: ScoreCard, ats, integrity, qa, critical: int, iterations: list[dict],
            stop: str) -> dict:
    return {
        "job_fit": report.job_fit.model_dump(mode="json"),
        "resume_alignment": alignment.model_dump(mode="json"),
        "ats_parsing": min(r.score for r in ats) if ats else None,
        "ats_by_extractor": {r.extractor: r.score for r in ats},
        "evidence_integrity": integrity.score,
        "qa": qa.score,
        "critical_issues": critical,
        "iterations": iterations,
        "stop_reason": stop,
        "match_report": report.model_dump(mode="json"),
    }


def _write_files(session: Session, settings: Settings, version: ResumeVersion, data: CandidateProfile,
                 resume: TailoredResume, pdf: bytes, docx: bytes, report: MatchReport, alignment: ScoreCard,
                 change_log: list[ChangeLogEntry], iterations: list[dict],
                 external: list[ExternalValidatorResult]) -> None:
    for f in list(version.files):
        delete_stored(settings, f.path)
        version.files.remove(f)
    session.flush()
    bundle = ValidationBundle.model_validate(version.validation)
    base = f"{_slug(resume.header.name)}_{_slug(resume.header.target_title)}_v{version.version_no}"
    files = {
        "pdf": (f"{base}.pdf", pdf),
        "docx": (f"{base}.docx", docx),
        "json": (f"{base}.json", json.dumps({"resume": resume.model_dump(mode="json"),
                                             "profile_revision_id": version.profile_revision_id}, indent=2).encode()),
        "match_report": (f"{base}_match_report.md", reports.match_report_md(report, alignment).encode()),
        "missing_skills": (f"{base}_missing_skills.md", reports.missing_skills_md(report, data).encode()),
        "change_log": (f"{base}_change_log.md", reports.change_log_md(change_log).encode()),
        "evidence_report": (f"{base}_evidence_integrity.md", reports.integrity_md(bundle.integrity, data).encode()),
        "evaluation_report": (f"{base}_evaluation_report.md", reports.evaluation_report_md(
            resume, report, alignment, bundle.ats, bundle.integrity, bundle.qa, external, iterations, change_log,
            data).encode()),
        "evaluation_json": (f"{base}_evaluation.json", json.dumps({
            "scores": {k: v for k, v in version.scores.items() if k != "match_report"},
            "match_report": report.model_dump(mode="json"), "validation": version.validation,
        }, indent=2, default=str).encode()),
    }
    for kind, (name, content) in files.items():
        path = store_output(settings, version.id, name, content)
        version.files.append(GeneratedFile(kind=kind, filename=name, path=str(path),
                                           sha256=sha256_bytes(content), size_bytes=len(content)))
    session.flush()


def get_version(session: Session, version_id: str) -> ResumeVersion:
    v = session.get(ResumeVersion, version_id)
    if not v:
        raise NotFound("Resume version not found")
    return v


def list_versions(session: Session, job_id: str | None = None) -> list[ResumeVersion]:
    q = select(ResumeVersion).order_by(ResumeVersion.created_at.desc())
    if job_id:
        q = q.where(ResumeVersion.job_id == job_id)
    return list(session.scalars(q))


def comparison(session: Session, version: ResumeVersion) -> dict:
    data = profiles.revision_data(session, version.profile_revision_id)
    resume = TailoredResume.model_validate(version.content)
    return {
        "original_text": original_plain_text(data),
        "tailored_text": resume_plain_text(resume),
        "bullets": [d.model_dump() for d in bullet_diffs(data, resume)],
        "omitted": [o.model_dump() for o in resume.omitted],
        "section_order": resume.section_order,
    }


# --------------------------------------------------------------------------- editing & approval

EDIT_OPS = {"set_bullet_text", "remove_bullet", "move_bullet", "restore_bullet", "set_target_title", "approve_bullet"}


def edit(session: Session, settings: Settings, version_id: str, ops: list[dict], today: date | None = None) -> ResumeVersion:
    """Apply editor operations and save the result as a new version (the old one is kept)."""
    old = get_version(session, version_id)
    data = profiles.revision_data(session, old.profile_revision_id)
    resume = TailoredResume.model_validate(old.content)
    change_log = [ChangeLogEntry.model_validate(c) for c in old.change_log]
    entries = [*resume.experience, *resume.projects]

    def find_bullet(bid: str):
        for e in entries:
            for i, b in enumerate(e.bullets):
                if b.id == bid:
                    return e, i, b
        raise NotFound(f"Bullet {bid} not found")

    for op in ops:
        kind = op.get("op")
        if kind not in EDIT_OPS:
            raise ValueError(f"Unknown edit operation: {kind}")
        if kind == "set_bullet_text":
            e, i, b = find_bullet(op["bullet_id"])
            text = " ".join(str(op["text"]).split())
            e.bullets[i] = b.model_copy(update={"text": text, "origin": "user", "approved": True, "variant_id": None})
            change_log.append(ChangeLogEntry(kind="bullet_reworded", target=b.id, before=b.text, after=text,
                                             reason="Edited by you in the resume editor (checked against the evidence).",
                                             evidence_ids=b.achievement_ids))
        elif kind == "remove_bullet":
            e, i, b = find_bullet(op["bullet_id"])
            e.bullets.pop(i)
            change_log.append(ChangeLogEntry(kind="bullet_removed", target=b.id, before=b.text,
                                             reason="Removed by you in the resume editor.", evidence_ids=b.achievement_ids))
        elif kind == "move_bullet":
            e, i, b = find_bullet(op["bullet_id"])
            to = max(0, min(int(op["to"]), len(e.bullets) - 1))
            e.bullets.insert(to, e.bullets.pop(i))
            change_log.append(ChangeLogEntry(kind="bullet_reordered", target=b.id, before=f"position {i + 1}",
                                             after=f"position {to + 1}", reason="Reordered by you."))
        elif kind == "approve_bullet":
            e, i, b = find_bullet(op["bullet_id"])
            e.bullets[i] = b.model_copy(update={"approved": True})
        elif kind == "restore_bullet":
            ach_id = op["achievement_id"]
            found = data.find_achievement(ach_id)
            if not found:
                raise NotFound("Achievement not found")
            ach, parent = found
            target = next((e for e in entries if getattr(e, "role_id", None) == parent.id
                           or getattr(e, "project_id", None) == parent.id), None)
            if target is None:
                raise ValueError("That role or project is not on this resume.")
            target.bullets.append(ResumeBullet(id=f"b-{ach.id}-restored", text=ach.text, achievement_ids=[ach.id],
                                               origin="original", approved=True))
            resume.omitted = [o for o in resume.omitted if o.item_id != ach_id]
            change_log.append(ChangeLogEntry(kind="revision", target=ach.id, after=ach.text,
                                             reason="Restored by you.", evidence_ids=[ach.id]))
        elif kind == "set_target_title":
            new_title = " ".join(str(op["title"]).split())[:120]
            change_log.append(ChangeLogEntry(kind="title", target="header", before=resume.header.target_title,
                                             after=new_title, reason="Target title set by you."))
            resume.header.target_title = new_title
    return _save_edited(session, settings, old, data, resume, change_log, today)


def _save_edited(session: Session, settings: Settings, old: ResumeVersion, data: CandidateProfile,
                 resume: TailoredResume, change_log: list[ChangeLogEntry], today: date | None) -> ResumeVersion:
    from app.render.fit import fit_resume

    if old.job_id:
        job = job_service.get_job(session, old.job_id)
        analysis = job_service.job_analysis(job)
        job_text = job.raw_text
    else:
        analysis = preset_job(old.variant) if old.variant else JobAnalysis(title=resume.header.target_title)
        job_text = ""
    report = MatchReport.model_validate(old.scores["match_report"])
    fitted, pdf, _ = fit_resume(resume)
    docx = render_docx(fitted)
    ats, integrity, qa, alignment = evaluate(data, analysis, report, fitted, pdf, docx, None, today)
    external = run_all(ValidationContext(resume=fitted, resume_text=resume_plain_text(fitted), pdf=pdf, docx=docx,
                                         job=analysis, job_text=job_text))
    latest = session.scalars(select(ResumeVersion).where(
        ResumeVersion.job_id == old.job_id if old.job_id else ResumeVersion.variant == old.variant)
        .order_by(ResumeVersion.version_no.desc())).first()
    critical = sum(1 for i in qa.issues if i.severity == "critical")
    iterations = [{"iteration": 1, "scores": {"resume_alignment": alignment.total, "ats_parsing": min(r.score for r in ats),
                                              "evidence_integrity": integrity.score, "qa": qa.score,
                                              "critical_issues": critical}, "actions": ["Edited in resume editor"],
                   "diagnoses": []}]
    version = ResumeVersion(job_id=old.job_id, profile_revision_id=old.profile_revision_id,
                            version_no=(latest.version_no if latest else old.version_no) + 1, parent_id=old.id,
                            variant=old.variant, status="draft", content=fitted.model_dump(mode="json"),
                            change_log=[c.model_dump(mode="json") for c in change_log],
                            scores=_scores(report, alignment, ats, integrity, qa, critical, iterations, "edited"),
                            validation=ValidationBundle(ats=ats, integrity=integrity, qa=qa,
                                                        external=external).model_dump(mode="json"))
    session.add(version)
    session.flush()
    _write_files(session, settings, version, data, fitted, pdf, docx, report, alignment, change_log, iterations, external)
    audit(session, "resume", version.id, "edited", {"parent": old.id})
    return version


def approve(session: Session, version_id: str) -> ResumeVersion:
    """Step 8: you approve the final changes. Blocked while any claim is unsupported."""
    v = get_version(session, version_id)
    bundle = ValidationBundle.model_validate(v.validation)
    if bundle.integrity.unsupported:
        raise ValueError("This version has unsupported claims. Fix or remove them before approving.")
    resume = TailoredResume.model_validate(v.content)
    for b in resume.all_bullets():
        b.approved = True
    v.content = resume.model_dump(mode="json")
    v.change_log = [{**c, "requires_approval": False} for c in v.change_log]
    v.status = "approved"
    from app.schemas.common import utcnow

    v.approved_at = utcnow()
    # Approved wording becomes approved in the master profile too (one new profile revision).
    used = [(b.achievement_ids[0], b.variant_id) for b in resume.all_bullets() if b.variant_id]
    newly = profiles.approve_variants(session, used, f"Approved {resume.header.target_title} resume v{v.version_no}")
    audit(session, "resume", v.id, "approved", {"variants_approved": newly})
    return v


def delete_version(session: Session, settings: Settings, version_id: str) -> None:
    v = get_version(session, version_id)
    for f in v.files:
        delete_stored(settings, f.path)
    session.delete(v)
    try:
        output_dir(settings, version_id).rmdir()
    except OSError:
        pass
    audit(session, "resume", version_id, "deleted")


def regenerate_pdf_preview(version: ResumeVersion) -> bytes:
    return render_pdf(TailoredResume.model_validate(version.content))
