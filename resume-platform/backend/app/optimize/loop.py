"""Generate -> Parse -> Evaluate -> Diagnose -> Revise -> Re-evaluate (at most three cycles).

Revisions are deterministic and conservative: they remove or replace content that fails a
check, surface evidence the profile already has, and never add anything new. The loop stops
early when nothing critical remains or when a cycle produces no substantive change; it does
not chase a higher number for its own sake.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.matching.engine import EvidenceIndex, achievement_relevance, assess_skill, score_resume_alignment
from app.render.docx_writer import render_docx
from app.render.fit import fit_resume
from app.schemas.common import stable_id
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, ScoreCard, Weights
from app.schemas.profile import CandidateProfile
from app.schemas.resume import ChangeLogEntry, OmittedItem, ResumeBullet, TailoredResume
from app.schemas.validation import ATSReport, IntegrityReport, QAReport
from app.tailoring.tailor import TailorOptions, TailorResult, choose_wording, sync_change_log, tailor
from app.validation import ats as ats_mod
from app.validation.integrity import check_integrity
from app.validation.qa import check_quality


@dataclass
class Diagnosis:
    code: str
    severity: str
    message: str
    target: str | None = None


@dataclass
class Iteration:
    number: int
    resume: TailoredResume
    pdf: bytes
    docx: bytes
    ats: list[ATSReport]
    integrity: IntegrityReport
    qa: QAReport
    alignment: ScoreCard
    diagnoses: list[Diagnosis]
    actions: list[str] = field(default_factory=list)

    @property
    def critical(self) -> int:
        return sum(1 for d in self.diagnoses if d.severity == "critical")

    def scores(self) -> dict:
        return {
            "resume_alignment": self.alignment.total,
            "ats_parsing": min(r.score for r in self.ats) if self.ats else None,
            "ats_by_extractor": {r.extractor: r.score for r in self.ats},
            "evidence_integrity": self.integrity.score,
            "qa": self.qa.score,
            "critical_issues": self.critical,
        }


@dataclass
class OptimizationResult:
    final: Iteration
    iterations: list[Iteration]
    change_log: list[ChangeLogEntry]
    stop_reason: str


def evaluate(profile: CandidateProfile, job: JobAnalysis, report: MatchReport | None, resume: TailoredResume,
             pdf: bytes, docx: bytes, weights: Weights | None, today: date | None,
             use_pdftotext: bool = True) -> tuple[list[ATSReport], IntegrityReport, QAReport, ScoreCard]:
    reports = [ats_mod.check_pdf(pdf, resume), ats_mod.check_docx(docx, resume)]
    if use_pdftotext:
        extra = ats_mod.check_pdf_with_pdftotext(pdf, resume)
        if extra:
            reports.append(extra)
    integrity = check_integrity(profile, resume)
    qa = check_quality(profile, resume, job, report, integrity, reports)
    alignment = score_resume_alignment(profile, job, resume, ats_score=min(r.score for r in reports),
                                       qa_score=qa.score, weights=weights, today=today)
    return reports, integrity, qa, alignment


def diagnose(profile: CandidateProfile, resume: TailoredResume, integrity: IntegrityReport, qa: QAReport) -> list[Diagnosis]:
    out: list[Diagnosis] = []
    for c in integrity.claims:
        if c.status in ("unsupported", "rejected_source"):
            out.append(Diagnosis("unsupported_claim", "critical", c.text, target=(c.source_ids or [None])[0]))
    for i in qa.issues:
        if i.code in ("academic_production_claim", "parse_failure", "employment_facts_changed"):
            out.append(Diagnosis(i.code, "critical", i.message, target=i.location))
        elif i.code in ("mandatory_not_shown", "keyword_repetition", "repeated_achievement", "long_bullet", "ai_tell"):
            out.append(Diagnosis(i.code, i.severity, i.message, target=i.location))
    return out


def revise(profile: CandidateProfile, job: JobAnalysis, resume: TailoredResume, diagnoses: list[Diagnosis],
           integrity: IntegrityReport, options: TailorOptions) -> tuple[TailoredResume, list[str], list[ChangeLogEntry]]:
    new = resume.model_copy(deep=True)
    actions: list[str] = []
    log: list[ChangeLogEntry] = []
    weights = {s.canonical: s.importance for s in job.skill_importance}
    bad_texts = {c.text for c in integrity.claims if c.status in ("unsupported", "rejected_source")}
    critical_spans = {d.message for d in diagnoses if d.code == "academic_production_claim"}

    def entries():
        yield from new.experience
        yield from new.projects

    # 1. Unsupported or production-in-academic bullets: fall back to wording that passes, else drop.
    for entry in entries():
        for b in list(entry.bullets):
            problem = b.text in bad_texts or any(f.kind == "academic_vs_production" for f in b.flags) \
                or any(b.text[:60] in m for m in critical_spans)
            if not problem:
                continue
            found = profile.find_achievement(b.achievement_ids[0])
            replaced = False
            if found:
                ach, parent = found
                alt = choose_wording(ach.model_copy(update={"variants": [v for v in ach.variants if v.text != b.text]}),
                                     parent, weights, options.use_unapproved_wording)
                if alt.text != b.text and not any(f.severity == "critical" for f in alt.flags):
                    idx = entry.bullets.index(b)
                    entry.bullets[idx] = b.model_copy(update={"text": alt.text, "variant_id": alt.variant_id,
                                                              "origin": alt.origin, "approved": alt.approved,
                                                              "flags": alt.flags})
                    actions.append(f"Replaced wording that failed a check: {b.text[:50]}...")
                    log.append(ChangeLogEntry(kind="revision", target=b.id, before=b.text, after=alt.text,
                                              reason="Previous wording failed the evidence or academic-claim check.",
                                              evidence_ids=b.achievement_ids, requires_approval=not alt.approved))
                    replaced = True
            if not replaced:
                entry.bullets.remove(b)
                new.omitted.append(OmittedItem(item_type="bullet", item_id=b.achievement_ids[0], text=b.text,
                                               reason="Removed: could not be stated without an unsupported claim"))
                actions.append(f"Removed bullet that could not be supported: {b.text[:50]}...")
                log.append(ChangeLogEntry(kind="bullet_removed", target=b.id, before=b.text, after=None,
                                          reason="Could not be worded without an unsupported claim.",
                                          evidence_ids=b.achievement_ids))
    # 2. A required skill the profile demonstrates but the page does not: bring in the best bullet.
    on_page = {i for b in new.all_bullets() for i in b.achievement_ids}
    idx_full = EvidenceIndex.build(profile)
    relevance = achievement_relevance(profile, job)
    for d in diagnoses:
        if d.code != "mandatory_not_shown":
            continue
        skill = d.message.split("'")[1] if "'" in d.message else ""
        canon = next((s.canonical for s in job.skill_importance if s.as_written == skill), skill)
        a = assess_skill(canon, idx_full)
        ach_ids = [e.target_id for e in a.evidence if e.target_type == "achievement" and e.target_id not in on_page]
        if not ach_ids:
            continue
        ach, parent = profile.find_achievement(ach_ids[0])  # type: ignore[misc]
        target_entry = next((e for e in entries() if getattr(e, "role_id", None) == parent.id
                             or getattr(e, "project_id", None) == parent.id), None)
        if target_entry is None:
            continue
        c = choose_wording(ach, parent, weights, options.use_unapproved_wording)
        rel, hits = relevance.get(ach.id, (0.0, []))
        target_entry.bullets.append(ResumeBullet(id=stable_id("b", ach.id, c.variant_id or "orig"), text=c.text,
                                                 achievement_ids=[ach.id], variant_id=c.variant_id, origin=c.origin,  # type: ignore[arg-type]
                                                 approved=c.approved, relevance=max(rel, 0.5),
                                                 matched_requirements=hits, flags=c.flags))
        target_entry.bullets.sort(key=lambda b: -b.relevance)
        new.omitted = [o for o in new.omitted if o.item_id != ach.id]
        on_page.add(ach.id)
        actions.append(f"Added evidence for required skill '{skill}'")
        log.append(ChangeLogEntry(kind="revision", target=ach.id, before=None, after=c.text,
                                  reason=f"'{skill}' is required and your profile shows it; it was missing from the page.",
                                  evidence_ids=[ach.id], requires_approval=not c.approved))
    return new, actions, log


def optimize(profile: CandidateProfile, job: JobAnalysis, report: MatchReport | None,
             options: TailorOptions | None = None, *, weights: Weights | None = None, max_cycles: int = 3,
             source_fonts: list[str] | None = None, variant: str | None = None,
             use_pdftotext: bool = True, base: TailorResult | None = None) -> OptimizationResult:
    options = options or TailorOptions()
    tr = base or tailor(profile, job, report, options, source_fonts=source_fonts, variant=variant)
    change_log = list(tr.change_log)
    iterations: list[Iteration] = []
    current = tr.resume
    stop = "max_cycles"
    for n in range(1, max(1, min(max_cycles, 3)) + 1):
        fitted, pdf, fit_actions = fit_resume(current, reserve_projects=tr.reserve_projects if n == 1 else None,
                                              reserve_bullets=tr.reserve_bullets if n == 1 else None)
        if n == 1:
            change_log = sync_change_log(profile, fitted, change_log)
        docx = render_docx(fitted)
        ats_reports, integrity, qa, alignment = evaluate(profile, job, report, fitted, pdf, docx, weights,
                                                          options.today, use_pdftotext)
        diagnoses = diagnose(profile, fitted, integrity, qa)
        it = Iteration(n, fitted, pdf, docx, ats_reports, integrity, qa, alignment, diagnoses, list(fit_actions))
        iterations.append(it)
        actionable = [d for d in diagnoses if d.severity == "critical" or d.code == "mandatory_not_shown"]
        if not actionable:
            stop = "no_critical_issues"
            break
        if n == max_cycles:
            break
        revised, actions, log = revise(profile, job, fitted, diagnoses, integrity, options)
        if not actions:
            stop = "no_further_improvement"
            break
        it.actions.extend(actions)
        change_log.extend(log)
        current = revised
    # Prefer the latest iteration unless it made things worse on truthfulness or parsing.
    best = min(iterations, key=lambda i: (i.critical, -i.integrity.score, -i.alignment.total, -i.number))
    return OptimizationResult(final=best, iterations=iterations, change_log=change_log, stop_reason=stop)
