"""Markdown reports: job match, missing skills, change log, evidence integrity, ATS parsing."""

from __future__ import annotations

from app.schemas.match import MatchReport, ScoreCard
from app.schemas.profile import CandidateProfile
from app.schemas.resume import ChangeLogEntry, TailoredResume
from app.schemas.validation import ATSReport, ExternalValidatorResult, IntegrityReport, QAReport

DISCLAIMER = ("_These numbers are transparent heuristics computed by this tool from your profile and the posting. "
              "They are not an employer's ATS score and do not predict your chance of an interview._")


def _esc(text: str | None) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def scorecard_md(card: ScoreCard) -> str:
    lines = [f"### {card.name}: {card.total:.1f} / 100", "", "| Dimension | Weight | Score | Points | How it is measured |",
             "|---|---:|---:|---:|---|"]
    for d in card.dimensions:
        lines.append(f"| {d.label} | {d.weight:g} | {d.score:.0%} | {d.points:.1f} | {_esc(d.explanation)} |")
    for d in card.dimensions:
        if d.details:
            lines += ["", f"**{d.label}**", *[f"- {_esc(x)}" for x in d.details[:10]]]
    if card.notes:
        lines += ["", *[f"> {n}" for n in card.notes]]
    return "\n".join(lines)


def match_report_md(report: MatchReport, alignment: ScoreCard | None = None) -> str:
    title = f"{report.job_title}" + (f" at {report.company}" if report.company else "")
    lines = [f"# Match report: {title}", "", DISCLAIMER, "", scorecard_md(report.job_fit), ""]
    if alignment:
        lines += [scorecard_md(alignment), ""]
    lines += ["## Eligibility gates", "", "Reported separately; never folded into a score.", ""]
    if report.gates:
        lines += ["| Gate | Status | Requirement | Explanation |", "|---|---|---|---|"]
        lines += [f"| {g.gate} | **{g.status.replace('_', ' ')}** | {_esc(g.requirement_text)} | {_esc(g.explanation)} |"
                  for g in report.gates]
    else:
        lines.append("No eligibility gates found in this posting.")
    lines += ["", "## Requirements and evidence", "",
              "| ID | Category | Requirement | Evidence | Explanation |", "|---|---|---|---|---|"]
    for m in report.requirement_matches:
        lines.append(f"| {m.requirement_id} | {m.category} | {_esc(m.requirement_text)} | {m.level_label} | "
                     f"{_esc(m.explanation)} |")
    lines += ["", "## Strongest matches", *[f"- {s}" for s in report.strengths or ["None directly demonstrated."]]]
    lines += ["", "## Missing mandatory qualifications", *[f"- {s}" for s in report.missing_mandatory or ["None."]]]
    lines += ["", "## Missing preferred qualifications", *[f"- {s}" for s in report.missing_preferred or ["None."]]]
    lines += ["", "## Recommendations", *[f"- {s}" for s in report.recommendations or ["None."]]]
    lines += ["", f"<sub>Scoring version {report.scoring_version}; input hash `{report.input_hash[:16]}`. "
                  "Identical inputs always produce identical scores.</sub>"]
    return "\n".join(lines)


def missing_skills_md(report: MatchReport, profile: CandidateProfile) -> str:
    lines = [f"# Missing skills: {report.job_title}", "",
             "Gaps are listed so you can decide what to learn or how to frame your application. Nothing here was "
             "added to your resume.", ""]
    gaps = [m for m in report.requirement_matches if m.category in ("mandatory", "preferred")]
    for title, levels in (("Not demonstrated", ("none",)), ("Related but not the same", ("related",)),
                          ("Listed but not shown in any bullet", ("partial",))):
        items = [m for m in gaps if m.level in levels]
        lines += [f"## {title}", ""]
        if not items:
            lines += ["None.", ""]
            continue
        for m in items:
            extra = ""
            if m.missing_skills:
                extra = f" (missing: {', '.join(m.missing_skills)})"
            elif m.related_skills:
                extra = f" (you have: {', '.join(m.related_skills)})"
            elif m.matched_skills:
                extra = f" ({', '.join(m.matched_skills)})"
            lines.append(f"- **{m.category}**: {m.requirement_text}{extra}")
        lines.append("")
    self_reported = [s.display for s in profile.skills if s.self_reported_only and not s.derived_from_bullets]
    if self_reported:
        lines += ["## Skills on your master resume with no supporting bullet", "",
                  "Add an example (what you built and the result) to turn these into demonstrated experience:", "",
                  ", ".join(self_reported), ""]
    return "\n".join(lines)


def change_log_md(entries: list[ChangeLogEntry]) -> str:
    lines = ["# Resume change log", "", "Every change from the master profile, with the reason and the evidence it "
             "relies on. Items marked **needs approval** use wording you have not approved yet.", ""]
    for e in entries:
        flag = " **(needs approval)**" if e.requires_approval else ""
        lines.append(f"### {e.kind.replace('_', ' ').title()}{flag}")
        lines.append(f"- Reason: {e.reason}")
        if e.before:
            lines.append(f"- Before: {e.before}")
        if e.after:
            lines.append(f"- After: {e.after}")
        if e.evidence_ids:
            lines.append(f"- Evidence: {', '.join(e.evidence_ids[:6])}")
        lines.append("")
    return "\n".join(lines)


def integrity_md(rep: IntegrityReport, profile: CandidateProfile) -> str:
    lines = ["# Evidence integrity report", "",
             f"- Claims traced to your profile: **{rep.score:.1f}%**",
             f"- Supported and verified by you: {rep.verified}",
             f"- Supported but not yet verified: {rep.unverified}",
             f"- Unsupported: {rep.unsupported}",
             f"- Employment facts unchanged: {'yes' if rep.employment_facts_preserved else '**NO**'}", ""]
    if rep.fact_problems:
        lines += ["## Problems", *[f"- {p}" for p in rep.fact_problems], ""]
    lines += ["## Claims", "", "| Section | Claim | Status | Source (original wording) |", "|---|---|---|---|"]
    for c in rep.claims:
        src = ""
        if c.source_ids:
            found = profile.find_achievement(c.source_ids[0])
            if found:
                src = found[0].original_text
        lines.append(f"| {c.location} | {_esc(c.text[:140])} | {c.status.replace('_', ' ')} | {_esc(src[:140])} |")
    return "\n".join(lines)


def ats_md(reports: list[ATSReport]) -> str:
    lines = ["# ATS parsing check", "", "Each generated file was extracted again and parsed field by field. "
             "This checks whether information survives extraction; it is not an employer's ATS score.", ""]
    for r in reports:
        lines += [f"## {r.extractor} ({r.document_kind.upper()}): {r.score:.1f} / 100", "",
                  "| Field | Expected | Extracted | Status |", "|---|---|---|---|"]
        for f in r.fields:
            lines.append(f"| {f.field} | {_esc(f.expected[:60])} | {_esc((f.extracted or '')[:60])} | {f.status} |")
        if r.checks:
            lines += ["", "| Format check | Status | Detail |", "|---|---|---|"]
            lines += [f"| {c.name} | {c.status} | {_esc(c.detail[:100])} |" for c in r.checks]
        lines.append("")
    return "\n".join(lines)


def qa_md(qa: QAReport) -> str:
    lines = [f"# Quality review: {qa.score:.0f} / 100", ""]
    if not qa.issues:
        return "\n".join(lines + ["No issues found."])
    for sev in ("critical", "warning", "info"):
        items = [i for i in qa.issues if i.severity == sev]
        if items:
            lines += [f"## {sev.title()} ({len(items)})", ""]
            lines += [f"- [{i.category}/{i.code}] {i.location}: {i.message}"
                      + (f" — {i.suggestion}" if i.suggestion else "") for i in items]
            lines.append("")
    return "\n".join(lines)


def external_md(results: list[ExternalValidatorResult]) -> str:
    lines = ["# Independent validators", "", "| Adapter | Type | Status | Score | Detail |", "|---|---|---|---:|---|"]
    for r in results:
        score = f"{r.score:.1f}" if r.score is not None else "n/a"
        lines.append(f"| {r.adapter} | {r.category} | {r.status} | {score} | {_esc(r.detail[:120])} |")
    lines += ["", "Scores appear only when a validator actually returned one. Unavailable services are listed, not "
                  "estimated."]
    return "\n".join(lines)


def evaluation_report_md(resume: TailoredResume, report: MatchReport, alignment: ScoreCard, ats: list[ATSReport],
                         integrity: IntegrityReport, qa: QAReport, external: list[ExternalValidatorResult],
                         iterations: list[dict], change_log: list[ChangeLogEntry], profile: CandidateProfile) -> str:
    parts = [
        f"# Evaluation report: {resume.header.target_title}" + (f" at {report.company}" if report.company else ""),
        "", DISCLAIMER, "",
        "## Summary", "",
        f"- Job fit (whole profile): **{report.job_fit.total:.1f}**",
        f"- Resume alignment (this resume): **{alignment.total:.1f}**",
        f"- ATS parsing (lowest extractor): **{min(r.score for r in ats):.1f}**" if ats else "- ATS parsing: not run",
        f"- Evidence integrity: **{integrity.score:.1f}%** ({integrity.unverified} claims still unverified)",
        f"- Quality review: **{qa.score:.0f}**", "",
        "## Revision cycles", "", "| Cycle | Alignment | ATS | Integrity | QA | Critical | Actions |",
        "|---:|---:|---:|---:|---:|---:|---|",
    ]
    for it in iterations:
        s = it["scores"]
        parts.append(f"| {it['iteration']} | {s['resume_alignment']:.1f} | {s['ats_parsing']:.1f} | "
                     f"{s['evidence_integrity']:.1f} | {s['qa']:.0f} | {s['critical_issues']} | "
                     f"{_esc('; '.join(it['actions'])[:200]) or '—'} |")
    parts += ["", match_report_md(report, alignment), "", qa_md(qa), "", integrity_md(integrity, profile), "",
              ats_md(ats), "", external_md(external), "", change_log_md(change_log)]
    return "\n".join(parts)
