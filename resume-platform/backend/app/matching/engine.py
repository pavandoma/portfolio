"""Evidence-based matching between a candidate profile and a job analysis.

Deterministic by design: the same profile, job and weights always produce the same report
(and the same ``input_hash``). The TF-IDF similarity is used only as a secondary signal next
to explicit skill evidence. Eligibility gates are evaluated separately and never folded into
the score; ambiguous gates are reported as "unclear" or "needs your input", never as a
rejection.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date

from app.core.dates import months_between
from app.core.taxonomy import get_taxonomy
from app.core.text import TfidfIndex, normalize_key
from app.schemas.job import JobAnalysis, Requirement
from app.schemas.match import (
    EVIDENCE_LEVEL_LABELS,
    DimensionScore,
    EvidenceLink,
    GateResult,
    MatchReport,
    RequirementMatch,
    ScoreCard,
    Weights,
)
from app.schemas.profile import Achievement, CandidateProfile, Project, Role

SCORING_VERSION = "match-1.0"
LEVEL_SCORE = {"direct": 1.0, "partial": 0.6, "related": 0.3, "none": 0.0, "unknown": 0.0}
LEVEL_RANK = {"direct": 4, "partial": 3, "related": 2, "unknown": 1, "none": 0}
DEGREE_RANK = {"certificate": 0, "associate": 1, "bachelor": 2, "master": 3, "doctorate": 4, "other": 0}
RELATED_FIELDS = {
    "computer science": ["artificial intelligence", "computer engineering", "software", "data science", "information",
                         "engineering science", "machine learning", "electrical", "mathematics", "statistics"],
    "artificial intelligence": ["computer science", "machine learning", "data science", "engineering science"],
    "data science": ["computer science", "statistics", "artificial intelligence", "mathematics", "engineering science"],
    "statistics": ["mathematics", "data science", "economics"],
    "engineering": ["engineering", "technology"],
}
QUANT_FIELDS = ["computer", "artificial intelligence", "data", "statistic", "math", "engineering", "physics", "economics",
                "technology", "science"]


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in sorted(obj.items())
                if k not in ("last_modified", "created_at", "added_at")}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def input_hash(profile: CandidateProfile, job: JobAnalysis, weights: Weights) -> str:
    payload = {
        "profile": _strip_volatile(profile.model_dump(mode="json")),
        "job": _strip_volatile(job.model_dump(mode="json")),
        "weights": weights.as_dict(),
        "version": SCORING_VERSION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass
class EvidenceIndex:
    """What the candidate can show, keyed by canonical skill."""

    demonstrated: dict[str, list[str]] = field(default_factory=dict)  # skill -> achievement ids
    listed: dict[str, str] = field(default_factory=dict)  # skill -> skill id (self-reported)
    certified: dict[str, str] = field(default_factory=dict)  # skill -> certification id
    achievements: dict[str, tuple[Achievement, Role | Project]] = field(default_factory=dict)

    @classmethod
    def build(cls, profile: CandidateProfile, achievement_ids: set[str] | None = None,
              skill_names: set[str] | None = None) -> EvidenceIndex:
        tax = get_taxonomy()
        idx = cls()
        for ach, parent in profile.usable_achievements():
            if achievement_ids is not None and ach.id not in achievement_ids:
                continue
            idx.achievements[ach.id] = (ach, parent)
            for s in ach.technologies + ach.competencies:
                idx.demonstrated.setdefault(s, []).append(ach.id)
        for s in profile.skills:
            if s.verification == "rejected":
                continue
            if skill_names is not None and s.name not in skill_names:
                continue
            idx.listed.setdefault(s.name, s.id)
        for c in profile.certifications:
            if c.verification == "rejected":
                continue
            for s in tax.find_canonical(f"{c.name} {c.detail or ''}"):
                idx.certified.setdefault(s, c.id)
        return idx

    def all_skills(self) -> set[str]:
        return set(self.demonstrated) | set(self.listed) | set(self.certified)


@dataclass
class SkillAssessment:
    required: str
    level: str
    score: float
    candidate_skill: str | None
    relation: str
    evidence: list[EvidenceLink]


def assess_skill(required: str, idx: EvidenceIndex) -> SkillAssessment:
    tax = get_taxonomy()
    best: SkillAssessment | None = None

    def consider(a: SkillAssessment) -> None:
        nonlocal best
        if best is None or (LEVEL_RANK[a.level], a.score) > (LEVEL_RANK[best.level], best.score):
            best = a

    for cand in sorted(idx.all_skills()):
        rel = tax.relationship(cand, required)
        if rel.relation == "none":
            continue
        ach_ids = idx.demonstrated.get(cand, [])
        if rel.relation in ("exact", "specific_satisfies_generic"):
            how = "" if rel.relation == "exact" else f" ({cand} is a kind of {required})"
            if ach_ids:
                ev = [EvidenceLink(target_type="achievement", target_id=a,
                                   excerpt=idx.achievements[a][0].text[:160],
                                   reason=f"Uses {cand}{how}", verification=idx.achievements[a][0].verification)
                      for a in ach_ids[:3]]
                consider(SkillAssessment(required, "direct", 1.0, cand, rel.relation, ev))
            elif cand in idx.certified:
                consider(SkillAssessment(required, "partial", 0.6, cand, rel.relation,
                                         [EvidenceLink(target_type="certification", target_id=idx.certified[cand],
                                                       reason=f"Certification covers {cand}{how}; no work example")]))
            elif cand in idx.listed:
                consider(SkillAssessment(required, "partial", 0.6, cand, rel.relation,
                                         [EvidenceLink(target_type="skill", target_id=idx.listed[cand],
                                                       reason=f"{cand} is listed in skills{how} but no bullet shows it")]))
        elif rel.relation == "sibling":
            score = 0.3 if ach_ids else 0.2
            consider(SkillAssessment(required, "related", score, cand, rel.relation,
                                     [EvidenceLink(target_type="skill", target_id=idx.listed.get(cand, cand),
                                                   reason=f"{cand} is related to {required} (both {rel.via}) but not interchangeable")]))
        elif rel.relation in ("generic_only", "related"):
            consider(SkillAssessment(required, "related", 0.25 if ach_ids else 0.15, cand, rel.relation,
                                     [EvidenceLink(target_type="skill", target_id=idx.listed.get(cand, cand),
                                                   reason=f"Has {cand}, which is broader/related; {required} itself is not shown")]))
    return best or SkillAssessment(required, "none", 0.0, None, "none", [])


def professional_months(profile: CandidateProfile, today: date | None = None,
                        role_filter=None) -> int:
    """Total months across roles, merging overlaps. Projects never count as professional experience."""
    spans = []
    for r in profile.roles:
        if r.verification == "rejected" or not r.start:
            continue
        if role_filter and not role_filter(r):
            continue
        sy, sm = (int(x) for x in r.start.split("-"))
        start = sy * 12 + sm
        end = start + months_between(r.start, r.end, today) - 1
        spans.append((start, end))
    spans.sort()
    total, cur = 0, None
    for s, e in spans:
        if cur is None or s > cur[1] + 1:
            if cur:
                total += cur[1] - cur[0] + 1
            cur = [s, e]
        else:
            cur[1] = max(cur[1], e)
    if cur:
        total += cur[1] - cur[0] + 1
    return total


def _field_matches(required_fields: list[str], candidate_fields: list[str], text: str) -> tuple[bool, str]:
    cand = [f.lower() for f in candidate_fields if f]
    generic = re.compile(r"quantitative|technical|stem|related|relevant|similar|any field", re.I)
    required_fields = [f for f in required_fields if not generic.search(f)]
    if not required_fields:
        if re.search(r"quantitative|technical|stem|related field", text, re.I):
            ok = any(any(q in c for q in QUANT_FIELDS) for c in cand)
            return ok, "quantitative/technical field" if ok else "field may not count as quantitative"
        return True, "no specific field required"
    lenient = bool(re.search(r"related|equivalent|similar", text, re.I))
    for req in required_fields:
        r = req.lower().strip()
        for c in cand:
            if r in c or c in r:
                return True, f"{c} matches {r}"
            if lenient:
                for key, related in RELATED_FIELDS.items():
                    if key in r and any(x in c for x in related):
                        return True, f"{c} is closely related to {r}"
    return False, "degree field differs from the listed fields"


def _semantic_index(profile: CandidateProfile, idx: EvidenceIndex) -> tuple[TfidfIndex, list[str]]:
    ids = list(idx.achievements)
    texts = [idx.achievements[a][0].text for a in ids]
    return TfidfIndex(texts or [""]), ids


def assess_requirement(req: Requirement, profile: CandidateProfile, idx: EvidenceIndex,
                       sem: tuple[TfidfIndex, list[str]], today: date | None = None) -> RequirementMatch:
    tax = get_taxonomy()
    level, score, explanation = "unknown", 0.0, ""
    evidence: list[EvidenceLink] = []
    matched, missing, related = [], [], []

    if req.kind == "experience_years":
        subject_skills = [s.canonical for s in req.skills]

        def relevant(role: Role) -> bool:
            if not subject_skills:
                return True
            role_skills = set()
            for a in role.achievements:
                if a.verification != "rejected":
                    for s in a.technologies + a.competencies:
                        role_skills.add(s)
                        role_skills.update(tax.ancestors(s))
            title_hits = set(tax.find_canonical(role.title))
            for t in list(title_hits):
                title_hits.update(tax.ancestors(t))
            if re.search(r"data engineer", role.title, re.I):
                title_hits.add("Data Engineering")
            return bool((role_skills | title_hits) & set(subject_skills))

        months_all = professional_months(profile, today)
        months_rel = professional_months(profile, today, relevant)
        years_rel = months_rel / 12
        need = req.years or 0
        evidence = [EvidenceLink(target_type="role", target_id=r.id, excerpt=f"{r.title}, {r.organization} ({r.date_text})",
                                 reason="Professional role counted toward years")
                    for r in profile.roles if r.verification != "rejected" and (not subject_skills or relevant(r))]
        if need <= 0:
            level, score = "unknown", 0.0
        elif years_rel >= need:
            level, score = "direct", 1.0
        elif years_rel >= need * 0.5:
            level, score = "partial", round(min(0.9, years_rel / need), 3)
        elif months_all > 0:
            level, score = "related", round(min(0.4, years_rel / need), 3)
        else:
            level, score = "none", 0.0
        explanation = (f"Requires {need:g}+ years{(' in ' + req.years_subject) if req.years_subject else ''}. "
                       f"Profile shows about {years_rel:.1f} years of relevant professional experience "
                       f"({months_all / 12:.1f} years in all roles). Academic projects are not counted as years.")
    elif req.kind == "education":
        best = None
        for e in profile.education:
            if e.verification == "rejected":
                continue
            if best is None or DEGREE_RANK.get(e.level, 0) > DEGREE_RANK.get(best.level, 0):
                best = e
        need_rank = DEGREE_RANK.get(req.degree_level or "bachelor", 2)
        if best is None:
            level, explanation = "none", "No education entries in the profile."
        else:
            have_rank = DEGREE_RANK.get(best.level, 0)
            fields = [e.field or e.degree for e in profile.education if e.verification != "rejected"]
            ok_field, why = _field_matches(req.degree_fields, fields, req.text)
            evidence = [EvidenceLink(target_type="education", target_id=e.id, excerpt=f"{e.degree}, {e.institution}",
                                     reason="Degree on record", verification=e.verification) for e in profile.education]
            if have_rank >= need_rank and ok_field:
                level, score = "direct", 1.0
            elif have_rank >= need_rank:
                level, score = "partial", 0.6
            elif re.search(r"equivalent experience|or equivalent", req.text, re.I):
                level, score = "partial", 0.5
            else:
                level, score = "none", 0.0
            explanation = f"Requires {req.degree_level or 'a'} degree. Highest on record: {best.degree} ({best.level}); {why}."
    elif req.kind in ("work_authorization", "clearance"):
        level, score = "unknown", 0.0
        explanation = "Eligibility requirement; evaluated as a gate, not scored."
    elif req.kind == "certification":
        found = []
        for c in profile.certifications:
            if c.verification == "rejected":
                continue
            cs = set(tax.find_canonical(f"{c.name} {c.detail or ''}"))
            for s in req.skills:
                if s.canonical in cs or any(tax.relationship(x, s.canonical).relation in ("exact", "specific_satisfies_generic") for x in cs):
                    found.append(c)
                    break
        if found:
            level, score = "direct", 1.0
            evidence = [EvidenceLink(target_type="certification", target_id=c.id, excerpt=c.name, reason="Certification on record",
                                     verification=c.verification) for c in found]
            explanation = f"Holds {', '.join(c.name for c in found)}."
        else:
            level, explanation = "none", "No matching certification on record."
    else:
        skill_results = [assess_skill(s.canonical, idx) for s in req.skills if tax.category(s.canonical) != "soft"]
        index, ids = sem
        sims = index.query(req.text) if ids else []
        best_sim, best_id = (max(zip(sims, ids, strict=True)) if sims else (0.0, None))
        if skill_results:
            if req.any_of:
                best = max(skill_results, key=lambda a: (LEVEL_RANK[a.level], a.score))
                level, score = best.level, best.score
                chosen = [best]
            else:
                score = sum(a.score for a in skill_results) / len(skill_results)
                levels = {a.level for a in skill_results}
                if levels == {"direct"}:
                    level = "direct"
                elif "direct" in levels or "partial" in levels:
                    level = "partial"
                elif "related" in levels:
                    level = "related"
                else:
                    level = "none"
                chosen = skill_results
            for a in chosen:
                evidence.extend(a.evidence)
            matched = [a.required for a in skill_results if a.level in ("direct", "partial")]
            missing = [a.required for a in skill_results if a.level == "none"]
            related = [f"{a.required} (~{a.candidate_skill})" for a in skill_results if a.level == "related"]
            if req.any_of and level in ("direct", "partial"):
                missing = []
            score = round(0.85 * score + 0.15 * min(1.0, best_sim / 0.4), 4)
            parts = []
            shown = [a.required + (f" (via {a.candidate_skill})" if a.candidate_skill not in (None, a.required) else "")
                     for a in skill_results if a.level == "direct"]
            listed = [a.required for a in skill_results if a.level == "partial"]
            if shown:
                parts.append(f"shown in your work: {', '.join(shown)}")
            if listed:
                parts.append(f"listed/certified but not shown in a bullet: {', '.join(listed)}")
            if related:
                parts.append(f"related only: {', '.join(related)}")
            if missing:
                parts.append(f"not shown: {', '.join(missing)}")
            explanation = ("Any one of the listed skills satisfies this. " if req.any_of else "") + "; ".join(parts) + "."
        else:
            # No explicit skills: fall back to text similarity with achievements (secondary signal).
            if best_id and best_sim >= 0.32:
                level, score = "partial", round(min(0.8, best_sim + 0.3), 4)
            elif best_id and best_sim >= 0.18:
                level, score = "related", round(best_sim, 4)
            elif req.kind in ("soft_skill", "other", "domain"):
                level, score = "unknown", 0.0
            else:
                level, score = "none", 0.0
            if best_id and level in ("partial", "related"):
                ach = idx.achievements[best_id][0]
                evidence.append(EvidenceLink(target_type="achievement", target_id=best_id, excerpt=ach.text[:160],
                                             reason=f"Similar wording (text similarity {best_sim:.2f})",
                                             verification=ach.verification))
            explanation = ("No specific skills named; judged by text similarity to your achievements"
                           f" (best {best_sim:.2f}).") if level != "unknown" else (
                "Cannot be assessed from the resume (soft skill, domain or general statement).")
            if req.kind == "domain":
                dom_hit = [a for a, (ach, _p) in idx.achievements.items()
                           if re.search(r"bank|financ|credit|health|retail|insur|logistic|marketing",
                                        ach.text, re.I) and re.search(
                               re.sub(r"[^a-z| ]", "", "|".join(req.text.lower().split()[:8])) or "zzz", ach.text, re.I)]
                if dom_hit:
                    level, score = "partial", 0.6
                    evidence = [EvidenceLink(target_type="achievement", target_id=dom_hit[0],
                                             excerpt=idx.achievements[dom_hit[0]][0].text[:160],
                                             reason="Mentions related domain context")]
                    explanation = "Domain appears in your project or work context."
    seen_targets: set[tuple[str, str]] = set()
    unique_evidence = []
    for e in evidence:
        if (e.target_type, e.target_id) not in seen_targets:
            seen_targets.add((e.target_type, e.target_id))
            unique_evidence.append(e)
    evidence = unique_evidence
    return RequirementMatch(
        requirement_id=req.id, requirement_text=req.text, category=req.category, kind=req.kind,
        importance=req.importance, level=level, level_label=EVIDENCE_LEVEL_LABELS[level], score=round(score, 4),
        explanation=explanation.strip(), matched_skills=matched, missing_skills=missing, related_skills=related,
        evidence=evidence,
    )


def evaluate_gates(job: JobAnalysis, profile: CandidateProfile, matches: dict[str, RequirementMatch]) -> list[GateResult]:
    gates: list[GateResult] = []
    wa = profile.work_authorization
    for req in job.requirements:
        if req.category != "mandatory":
            continue
        m = matches.get(req.id)
        if req.kind == "work_authorization":
            auth = next((a for a in job.authorization if a.text == req.text), None)
            restriction = auth.restriction if auth else "other"
            if wa.status == "unknown":
                gates.append(GateResult(gate="work_authorization", requirement_id=req.id, requirement_text=req.text,
                                        status="needs_user_input",
                                        explanation="Your work authorization is not recorded. Add it to the profile to evaluate this."))
            elif restriction == "no_sponsorship" and wa.status in ("requires_sponsorship", "authorized_requires_future_sponsorship"):
                gates.append(GateResult(gate="work_authorization", requirement_id=req.id, requirement_text=req.text,
                                        status="not_met", explanation="The posting says it cannot sponsor; your profile says sponsorship is (or will be) needed."))
            elif restriction == "citizenship" and wa.status not in ("citizen", "permanent_resident"):
                gates.append(GateResult(gate="work_authorization", requirement_id=req.id, requirement_text=req.text,
                                        status="unclear", explanation="The posting mentions citizenship/permanent residence; check the exact wording."))
            else:
                gates.append(GateResult(gate="work_authorization", requirement_id=req.id, requirement_text=req.text,
                                        status="met", explanation=f"Profile work authorization: {wa.status}."))
        elif req.kind == "clearance":
            has = wa.has_security_clearance
            gates.append(GateResult(gate="clearance", requirement_id=req.id, requirement_text=req.text,
                                    status="needs_user_input" if has is None else ("met" if has else "not_met"),
                                    explanation="Security clearance requirement."))
        elif req.kind == "experience_years" and m:
            if m.level == "direct":
                status = "met"
            elif any(r.employment_type == "unknown" for r in profile.roles):
                status = "unclear"
            else:
                status = "not_met" if m.level in ("none", "related") else "unclear"
            note = "" if status != "unclear" else " Employment type of at least one role is unconfirmed, and many postings accept equivalent academic or project work; read the wording."
            gates.append(GateResult(gate="minimum_experience", requirement_id=req.id, requirement_text=req.text,
                                    status=status, explanation=m.explanation + note))
        elif req.kind == "education" and m:
            status = {"direct": "met", "partial": "unclear"}.get(m.level, "not_met")
            gates.append(GateResult(gate="education", requirement_id=req.id, requirement_text=req.text, status=status,
                                    explanation=m.explanation))
        elif req.kind in ("certification", "license") and m and re.search(r"\b(required|must)\b", req.text, re.I):
            gates.append(GateResult(gate="credential", requirement_id=req.id, requirement_text=req.text,
                                    status="met" if m.level == "direct" else "not_met", explanation=m.explanation))
    return gates


def achievement_relevance(profile: CandidateProfile, job: JobAnalysis) -> dict[str, tuple[float, list[str]]]:
    """Score every usable achievement against the job (used for ordering and selection)."""
    tax = get_taxonomy()
    usable = profile.usable_achievements()
    if not usable:
        return {}
    index = TfidfIndex([a.text for a, _ in usable])
    reqs = [r for r in job.requirements if r.category != "context" and r.kind not in ("work_authorization", "clearance")]
    raw: dict[str, tuple[float, list[str]]] = {}
    sims_by_req = {r.id: index.query(r.text) for r in reqs}
    for i, (ach, _parent) in enumerate(usable):
        skills = set(ach.technologies + ach.competencies)
        total, hits = 0.0, []
        for r in reqs:
            credit = 0.0
            for s in r.skills:
                for c in skills:
                    rel = tax.relationship(c, s.canonical).relation
                    if rel in ("exact", "specific_satisfies_generic"):
                        credit = max(credit, 1.0)
                    elif rel == "sibling":
                        credit = max(credit, 0.25)
            credit = max(credit, min(1.0, sims_by_req[r.id][i] / 0.45) * 0.6)
            if credit > 0.2:
                hits.append(r.id)
            total += credit * r.importance
        raw[ach.id] = (total, hits)
    top = max(v[0] for v in raw.values()) or 1.0
    return {k: (round(v[0] / top, 4), v[1]) for k, v in raw.items()}


def _impact_score(ach_list: list[Achievement]) -> tuple[float, list[str]]:
    if not ach_list:
        return 0.0, ["No relevant achievements to assess."]
    credit = 0.0
    details = []
    for a in ach_list:
        if a.metrics:
            c = 1.0 if a.verification in ("verified", "user_corrected") else 0.75
            credit += c
            details.append(f"{'Verified' if c == 1.0 else 'Unverified'} metric: {a.metrics[0].raw} — {a.text[:70]}...")
    return credit / len(ach_list), details


def score_profile(profile: CandidateProfile, job: JobAnalysis, weights: Weights | None = None,
                  today: date | None = None) -> MatchReport:
    weights = weights or Weights()
    idx = EvidenceIndex.build(profile)
    sem = _semantic_index(profile, idx)
    matches = [assess_requirement(r, profile, idx, sem, today) for r in job.requirements if r.category != "context"]
    by_id = {m.requirement_id: m for m in matches}
    gates = evaluate_gates(job, profile, by_id)
    relevance = achievement_relevance(profile, job)
    dims = _dimensions(profile, job, matches, idx, relevance, weights, today, include_presentation=False)
    total_w = sum(d.weight for d in dims) or 1.0
    points = sum(d.points for d in dims)
    total = round(points / total_w * 100, 1)
    card = ScoreCard(name="Job Fit", total=total, dimensions=dims,
                     notes=[f"{points:.1f} of the {total_w:g} points that apply to a profile, scaled to 100.",
                            "Computed from the whole master profile, including unverified claims (flagged).",
                            "ATS parsing and clarity are resume properties and are scored on each generated resume instead."])
    mandatory = [m for m in matches if m.category == "mandatory" and m.kind not in ("work_authorization", "clearance")]
    preferred = [m for m in matches if m.category == "preferred"]
    strengths = [m.requirement_text for m in sorted(mandatory + preferred, key=lambda m: (-m.importance, m.requirement_id))
                 if m.level == "direct"][:3]
    missing_mand = [m.requirement_text for m in mandatory if m.level in ("none", "related")]
    missing_pref = [m.requirement_text for m in preferred if m.level in ("none", "related")]
    return MatchReport(
        job_title=job.title, company=job.company, job_fit=card, requirement_matches=matches, gates=gates,
        strengths=strengths, missing_mandatory=missing_mand, missing_preferred=missing_pref,
        recommendations=_recommendations(matches, gates, idx), weights=weights, scoring_version=SCORING_VERSION,
        input_hash=input_hash(profile, job, weights),
    )


def _dimensions(profile, job, matches, idx: EvidenceIndex, relevance, weights: Weights, today,
                include_presentation: bool, keyword_text: str | None = None) -> list[DimensionScore]:
    tax = get_taxonomy()
    scorable = [m for m in matches if m.kind not in ("work_authorization", "clearance") and m.level != "unknown"]
    mand = [m for m in scorable if m.category == "mandatory"]
    resp = [m for m in scorable if m.category in ("responsibility",)]
    pref = [m for m in scorable if m.category == "preferred"]

    def wavg(items):
        w = sum(m.importance for m in items)
        return (sum(m.score * m.importance for m in items) / w) if w else None

    req_score = wavg(mand)
    req_details = [f"{m.level_label}: {m.requirement_text[:90]}" for m in sorted(mand, key=lambda m: -m.importance)]
    if req_score is None:
        req_score = wavg(pref) or 0.0
        req_details.append("No mandatory requirements detected; used preferred requirements.")

    # Experience relevance: responsibilities matched by achievements, projects discounted.
    resp_items = []
    for m in resp + pref:
        s = m.score
        ach_ev = [e for e in m.evidence if e.target_type == "achievement"]
        if ach_ev and all(isinstance(idx.achievements.get(e.target_id, (None, None))[1], Project) for e in ach_ev):
            s *= 0.8
        resp_items.append((m, s))
    w = sum(m.importance for m, _ in resp_items)
    exp_core = (sum(s * m.importance for m, s in resp_items) / w) if w else (req_score or 0.0)
    years_needed = job.min_years_experience
    years_have = professional_months(profile, today) / 12
    years_ratio = 1.0 if not years_needed else min(1.0, years_have / years_needed)
    exp_score = 0.75 * exp_core + 0.25 * years_ratio
    exp_details = [f"Responsibilities/preferred matched: {exp_core:.0%} (project-only evidence counted at 80%).",
                   f"Professional experience: {years_have:.1f} years" + (f" vs {years_needed:g}+ requested." if years_needed else ".")]

    # Keyword coverage of the posting's important skills.
    ranked = [s for s in job.skill_importance if s.importance >= 0.15 and tax.category(s.canonical) != "soft"]
    cov_total = sum(s.importance for s in ranked) or 1.0
    cov = 0.0
    missing_kw = []
    text_lower = (keyword_text or "").lower()
    for s in ranked:
        a = assess_skill(s.canonical, idx)
        credit = {"direct": 1.0, "partial": 0.8, "related": 0.3}.get(a.level, 0.0)
        if keyword_text is not None and credit > 0:
            forms = [s.as_written.lower(), s.canonical.lower()] + [x.lower() for x in tax.nodes.get(s.canonical).aliases] \
                if s.canonical in tax.nodes else [s.as_written.lower()]
            if a.candidate_skill:
                forms.append(a.candidate_skill.lower())
            if not any(re.search(r"(?<![a-z0-9])" + re.escape(f) + r"(?![a-z0-9])", text_lower) for f in forms if f):
                credit *= 0.3  # the candidate has it, but the resume does not say so
        cov += credit * s.importance
        if credit < 0.3:
            missing_kw.append(s.as_written)
    kw_score = cov / cov_total if ranked else 0.0
    kw_details = [f"Covers {kw_score:.0%} of the posting's weighted skills."]
    if missing_kw:
        kw_details.append("Not covered: " + ", ".join(missing_kw[:10]))

    top_ids = [a for a, (score, _h) in sorted(relevance.items(), key=lambda kv: (-kv[1][0], kv[0]))
               if a in idx.achievements][:6]
    impact, impact_details = _impact_score([idx.achievements[a][0] for a in top_ids])

    dims = [
        DimensionScore(key="required", label="Required skills and qualifications", weight=weights.required,
                       score=round(req_score, 4), points=round(weights.required * req_score, 2),
                       explanation="Importance-weighted evidence for mandatory requirements.", details=req_details[:12]),
        DimensionScore(key="experience", label="Relevant experience and projects", weight=weights.experience,
                       score=round(exp_score, 4), points=round(weights.experience * exp_score, 2),
                       explanation="How well past work matches the responsibilities, plus years of professional experience.",
                       details=exp_details),
        DimensionScore(key="keywords", label="Technical keyword coverage", weight=weights.keywords,
                       score=round(kw_score, 4), points=round(weights.keywords * kw_score, 2),
                       explanation="Share of the posting's important skills the candidate can truthfully claim"
                                   + (" and the resume actually mentions." if keyword_text is not None else "."),
                       details=kw_details),
        DimensionScore(key="impact", label="Measurable impact", weight=weights.impact, score=round(impact, 4),
                       points=round(weights.impact * impact, 2),
                       explanation="Share of the most relevant achievements that include a result with a number "
                                   "(unverified numbers earn 75% credit).", details=impact_details[:6]),
    ]
    return dims


def _recommendations(matches: list[RequirementMatch], gates: list[GateResult], idx: EvidenceIndex) -> list[str]:
    recs: list[str] = []
    for g in gates:
        if g.status == "needs_user_input":
            recs.append(f"Answer in your profile: {g.explanation}")
        elif g.status == "not_met":
            recs.append(f"Eligibility gap ({g.gate}): {g.requirement_text}")
        elif g.status == "unclear":
            recs.append(f"Check eligibility ({g.gate}): {g.requirement_text}")
    for m in sorted(matches, key=lambda m: (-m.importance, m.requirement_id)):
        if m.category not in ("mandatory", "preferred") or m.kind in ("work_authorization", "clearance", "experience_years", "education"):
            continue
        if m.level == "partial" and any(e.target_type == "skill" for e in m.evidence):
            names = ", ".join(m.matched_skills) or m.requirement_text[:60]
            recs.append(f"{names}: listed as a skill but not shown in any bullet. If you have used it, add one concrete "
                        "example to your profile (what you built, with what result).")
        elif m.level in ("none", "related") and m.category == "mandatory":
            what = ", ".join(m.missing_skills or [m.requirement_text[:80]])
            recs.append(f"Gap: {what}. Do not add it unless you have real experience; if you do, record evidence first.")
    unverified = [a for a, (ach, _p) in idx.achievements.items() if ach.metrics and ach.verification == "unverified"]
    if unverified:
        recs.append(f"{len(unverified)} achievements contain unverified numbers. Confirm them so they can be "
                    "used with confidence.")
    seen, out = set(), []
    for r in recs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out[:15]


def requirement_key(company: str | None, title: str | None, location: str | None) -> str:
    return "|".join(normalize_key(x or "") for x in (company, title, location))


def score_resume_alignment(profile: CandidateProfile, job: JobAnalysis, resume, *, ats_score: float, qa_score: float,
                           weights: Weights | None = None, today: date | None = None) -> ScoreCard:
    """How well a specific resume communicates the candidate's fit (only what is on the page counts)."""
    from app.tailoring.diff import resume_plain_text

    weights = weights or Weights()
    tax = get_taxonomy()
    on_page = {i for b in resume.all_bullets() for i in b.achievement_ids}
    listed = set()
    for line in resume.skills:
        for item in line.items:
            canon = tax.canonical(item)
            if canon:
                listed.add(canon)
            for sid in line.sources.get(item, []):
                s = next((x for x in profile.skills if x.id == sid), None)
                if s:
                    listed.add(s.name)
    idx = EvidenceIndex.build(profile, achievement_ids=on_page, skill_names=listed)
    idx.certified = {k: v for k, v in EvidenceIndex.build(profile).certified.items()
                     if any(c.certification_id == v for c in resume.certifications)}
    sem = _semantic_index(profile, idx)
    matches = [assess_requirement(r, profile, idx, sem, today) for r in job.requirements if r.category != "context"]
    relevance = {k: v for k, v in achievement_relevance(profile, job).items() if k in on_page}
    dims = _dimensions(profile, job, matches, idx, relevance, weights, today, include_presentation=True,
                       keyword_text=resume_plain_text(resume))
    dims.append(DimensionScore(key="ats", label="ATS parsing and formatting", weight=weights.ats,
                               score=round(ats_score / 100, 4), points=round(weights.ats * ats_score / 100, 2),
                               explanation="Field-level parse-back of the rendered files (lowest of the extractors run)."))
    dims.append(DimensionScore(key="clarity", label="Clarity and conciseness", weight=weights.clarity,
                               score=round(qa_score / 100, 4), points=round(weights.clarity * qa_score / 100, 2),
                               explanation="Style and content QA: bullet length, tense, filler, repetition."))
    total_w = sum(d.weight for d in dims) or 1.0
    return ScoreCard(name="Resume Alignment", total=round(sum(d.points for d in dims) / total_w * 100, 1),
                     dimensions=dims,
                     notes=["Only content that appears on this resume counts.",
                            "Not an employer's ATS score and not a prediction of interview chances."])
