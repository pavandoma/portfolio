"""Content, style and formatting QA for a tailored resume."""

from __future__ import annotations

import re

from app.core.taxonomy import get_taxonomy
from app.core.text import jaccard, tokenize, word_count
from app.ingest.claims import AWKWARD_PATTERNS, PERCENT_RE, PRODUCTION_RE
from app.matching.engine import EvidenceIndex, assess_skill, professional_months
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.profile import CandidateProfile
from app.schemas.resume import TailoredResume
from app.schemas.validation import ATSReport, IntegrityReport, QAIssue, QAReport
from app.tailoring.diff import resume_plain_text
from app.tailoring.style import IRREGULAR_PAST, STRONG_VERBS, WEAK_OPENERS, ai_tells, first_word, keyword_repetition

COMMON_ACRONYMS = {"AI", "ML", "SQL", "AWS", "ETL", "ELT", "KPI", "KPIS", "CTE", "CTES", "API", "APIS", "NLP", "LLM", "LLMS",
                   "RAG", "ECS", "EC2", "GPA", "USA", "US", "UK", "BI", "MS", "BS", "PHD", "CEO", "IT", "UI", "UX",
                   "CI", "CD", "QA", "SUNY", "SRM", "GCP", "ID", "PDF", "CSV", "JSON", "HR", "ROI", "SLA", "NY", "CA",
                   "TX", "MA", "OH", "IL", "WA", "GPU", "CPU", "MLOPS", "DOCX", "S3", "B2B", "SAAS", "IOT", "R"}
OUTCOME_WORDS = re.compile(r"\b(reduc|improv|increas|cut|rais|sav|lower|shorten|grew|grow|boost|accelerat|achiev|reach|"
                           r"enabl|kept|keep|let|allow|speed|faster|fewer|less|more)\w*", re.I)
SEVERITY_COST = {"critical": 15, "warning": 4, "info": 1}


def _is_past_tense(word: str) -> bool:
    w = word.lower()
    return w.endswith("ed") or w in IRREGULAR_PAST.values() or w in {"built", "led", "ran", "wrote", "cut", "set", "made"}


def check_quality(profile: CandidateProfile, resume: TailoredResume, job: JobAnalysis | None = None,
                  report: MatchReport | None = None, integrity: IntegrityReport | None = None,
                  ats_reports: list[ATSReport] | None = None) -> QAReport:
    issues: list[QAIssue] = []
    tax = get_taxonomy()
    bullets = [(f"{e.title} @ {e.organization}", b, e) for e in resume.experience for b in e.bullets] + \
              [(p.name, b, p) for p in resume.projects for b in p.bullets]

    # ---- content ------------------------------------------------------------
    if integrity:
        for c in integrity.claims:
            if c.status in ("unsupported", "rejected_source"):
                issues.append(QAIssue(category="content", code="unsupported_claim", severity="critical",
                                      location=c.location, message=f"Not supported by the profile: {c.text[:90]}",
                                      suggestion=c.detail or "Remove it or add evidence to the profile first."))
        if not integrity.employment_facts_preserved:
            issues.append(QAIssue(category="content", code="employment_facts_changed", severity="critical",
                                  location="experience", message="An employer, title, location or date differs from the profile."))
    for where, b, parent in bullets:
        for f in b.flags:
            if f.kind == "academic_vs_production":
                issues.append(QAIssue(category="content", code="academic_production_claim", severity="critical",
                                      location=where, message=f"'{f.span}' implies production use in an academic project.",
                                      suggestion="Use wording that describes what was built and tested."))
        academic = getattr(parent, "descriptor", None) in ("Academic project", "Personal project")
        if academic and PRODUCTION_RE.search(b.text) and not any(f.kind == "academic_vs_production" for f in b.flags):
            issues.append(QAIssue(category="content", code="academic_production_claim", severity="critical",
                                  location=where, message=f"Production wording in an academic project: {b.text[:80]}"))
    if job and report:
        idx_resume = EvidenceIndex.build(profile, {i for b in resume.all_bullets() for i in b.achievement_ids})
        idx_full = EvidenceIndex.build(profile)
        for m in report.requirement_matches:
            if m.category != "mandatory" or m.kind not in ("skill",):
                continue
            req = next((r for r in job.requirements if r.id == m.requirement_id), None)
            if not req or not req.skills:
                continue
            for s in req.skills:
                full = assess_skill(s.canonical, idx_full)
                on_resume = assess_skill(s.canonical, idx_resume)
                if full.level == "direct" and on_resume.level != "direct":
                    issues.append(QAIssue(category="content", code="mandatory_not_shown", severity="warning",
                                          location="experience",
                                          message=f"'{s.as_written}' is required and your profile shows it, but no bullet on "
                                                  "this resume does.",
                                          suggestion="Include a bullet that demonstrates it."))
            if m.level in ("none", "related"):
                issues.append(QAIssue(category="content", code="mandatory_gap", severity="info", location="job match",
                                      message=f"Requirement not met by your profile: {m.requirement_text[:90]}",
                                      suggestion="This is a real gap; it is reported, never invented."))
    texts = [b.text for _w, b, _p in bullets]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if jaccard(tokenize(texts[i]), tokenize(texts[j])) > 0.6:
                issues.append(QAIssue(category="content", code="repeated_achievement", severity="warning",
                                      location=bullets[j][0], message=f"Bullets overlap heavily: '{texts[j][:60]}...'"))
    summary_text = resume.summary_text
    for t in texts:
        if t.rstrip(".") and t.rstrip(".") in summary_text:
            issues.append(QAIssue(category="style", code="summary_repeats_bullet", severity="info", location="summary",
                                  message="The summary repeats a bullet word for word.",
                                  suggestion="Use a shorter phrasing of the result in the summary."))
    plain = resume_plain_text(resume)
    known_forms = {f.upper() for n in tax.nodes.values() for f in [n.name, *n.aliases]}
    acronyms = set(re.findall(r"\b[A-Z][A-Z0-9]{1,6}s?\b", " ".join(texts) + " " + summary_text))
    unknown = sorted(a for a in acronyms if a.upper() not in COMMON_ACRONYMS and a.upper() not in known_forms
                     and a.rstrip("s").upper() not in COMMON_ACRONYMS and a.rstrip("s").upper() not in known_forms)
    for a in unknown:
        issues.append(QAIssue(category="content", code="unexplained_abbreviation", severity="info", location="resume",
                              message=f"Abbreviation '{a}' may not be familiar to every reader.",
                              suggestion="Spell it out once or use the common term."))
    if job:
        kws = [s.as_written for s in job.skill_importance[:15]]
        for kw, n in keyword_repetition(texts + [summary_text], kws, limit=5).items():
            issues.append(QAIssue(category="style", code="keyword_repetition", severity="warning", location="resume",
                                  message=f"'{kw}' appears {n} times; repetition reads as keyword stuffing."))
    with_numbers = sum(1 for t in texts if re.search(r"\d", t))
    if texts and with_numbers / len(texts) < 0.5:
        issues.append(QAIssue(category="content", code="few_measurable_results", severity="info", location="resume",
                              message=f"{with_numbers} of {len(texts)} bullets include a number.",
                              suggestion="Add real numbers to the profile where you have them; never estimate."))
    for where, b, parent in bullets:
        if not re.search(r"\d", b.text) and not OUTCOME_WORDS.search(b.text):
            issues.append(QAIssue(category="content", code="missing_outcome", severity="info", location=where,
                                  message=f"No outcome stated: '{b.text[:70]}...'"))

    # ---- style --------------------------------------------------------------
    for where, b, parent in bullets:
        n = word_count(b.text)
        if n > 35:
            issues.append(QAIssue(category="style", code="long_bullet", severity="warning", location=where,
                                  message=f"{n} words; aim for 15-25 where practical.", suggestion=b.text[:60]))
        elif n < 8:
            issues.append(QAIssue(category="style", code="short_bullet", severity="info", location=where,
                                  message=f"Only {n} words; add what changed as a result."))
        for phrase, why in ai_tells(b.text):
            issues.append(QAIssue(category="style", code="ai_tell", severity="warning", location=where,
                                  message=f"'{phrase}': {why}"))
        if WEAK_OPENERS.match(b.text):
            issues.append(QAIssue(category="style", code="weak_opener", severity="warning", location=where,
                                  message=f"Starts with a weak phrase: '{b.text[:30]}'", suggestion="Start with an action verb."))
        for rx, msg in AWKWARD_PATTERNS:
            if rx.search(b.text):
                issues.append(QAIssue(category="style", code="grammar", severity="warning", location=where, message=msg))
        fw = first_word(b.text)
        is_current = getattr(parent, "date_range", "").endswith("Present")
        if not is_current and fw and not _is_past_tense(fw) and fw not in STRONG_VERBS:
            issues.append(QAIssue(category="style", code="tense", severity="info", location=where,
                                  message=f"Past roles read best in past tense ('{fw}')."))
        if re.search(r"\s{2,}|\s[,.;]|\b(\w+) \1\b", b.text):
            issues.append(QAIssue(category="style", code="spacing_or_repeated_word", severity="info", location=where,
                                  message="Extra spaces or a repeated word."))
    for phrase, why in ai_tells(summary_text):
        issues.append(QAIssue(category="style", code="ai_tell", severity="warning", location="summary",
                              message=f"'{phrase}': {why}"))
    openers = {}
    for _w, b, _p in bullets:
        openers.setdefault(first_word(b.text), []).append(b.text)
    for w, items in openers.items():
        if w and len(items) >= 3:
            issues.append(QAIssue(category="style", code="repeated_opener", severity="info", location="resume",
                                  message=f"{len(items)} bullets start with '{w}'. Vary the verbs."))
    endings = {t.rstrip()[-1:] == "." for t in texts}
    if len(endings) > 1:
        issues.append(QAIssue(category="style", code="inconsistent_punctuation", severity="info", location="resume",
                              message="Some bullets end with a period and some do not."))
    n_sent = len(resume.summary)
    if n_sent and (n_sent < 2 or n_sent > 4 or word_count(summary_text) > 80):
        issues.append(QAIssue(category="style", code="summary_length", severity="warning", location="summary",
                              message="Summary should be 3-4 short sentences."))
    if resume.summary and not re.search(r"\d", summary_text):
        issues.append(QAIssue(category="content", code="summary_without_number", severity="info", location="summary",
                              message="The summary has no measured result (none could be traced to a short achievement)."))
    if job and resume.header.target_title.lower() not in job.title.lower():
        issues.append(QAIssue(category="content", code="title_mismatch", severity="warning", location="header",
                              message=f"Target title '{resume.header.target_title}' differs from the posting '{job.title}'."))
    if job and job.seniority in ("senior", "staff", "principal", "lead", "manager"):
        years = professional_months(profile) / 12
        if years < 3:
            issues.append(QAIssue(category="content", code="seniority_gap", severity="warning", location="header",
                                  message=f"The posting is {job.seniority}-level and your profile shows {years:.1f} years "
                                          "of professional experience. Only use a title you can back up in the interview."))
    dates = [e.date_range for e in resume.experience] + [e.date for e in resume.education]
    fmts = {("mon" if re.search(r"[A-Z][a-z]{2} \d{4}", d) else "other") for d in dates if d}
    if len(fmts) > 1:
        issues.append(QAIssue(category="formatting", code="inconsistent_dates", severity="warning", location="resume",
                              message="Dates use more than one format."))

    # ---- formatting (from the parse-back) -------------------------------------
    for rep in ats_reports or []:
        for f in rep.fields:
            if f.status == "fail":
                issues.append(QAIssue(category="formatting", code="parse_failure", severity="critical",
                                      location=f"{rep.extractor}: {f.field}",
                                      message=f"Expected '{f.expected}', extracted '{f.extracted}'. {f.detail}".strip()))
        for c in rep.checks:
            if c.status == "fail":
                issues.append(QAIssue(category="formatting", code=c.name, severity="warning",
                                      location=rep.extractor, message=c.detail))
            elif c.status == "warn":
                issues.append(QAIssue(category="formatting", code=c.name, severity="info", location=rep.extractor,
                                      message=c.detail))
    # De-duplicate identical messages
    seen, unique = set(), []
    for i in issues:
        key = (i.code, i.location, i.message)
        if key not in seen:
            seen.add(key)
            unique.append(i)
    style_content = [i for i in unique if i.category != "formatting"]
    score = max(0.0, 100.0 - sum(SEVERITY_COST[i.severity] for i in style_content if i.code != "mandatory_gap"))
    return QAReport(score=round(score, 1), issues=unique)


def percent_claims(text: str) -> int:
    return len(PERCENT_RE.findall(text))
