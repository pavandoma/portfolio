"""Tailoring engine: builds a targeted resume from the master profile and a job analysis.

Recruiter-psychology rules (from the Recruiter Psychology Playbook and the resume template):
  * the posting's exact title sits directly under the name (it is the target, not a past title);
  * a 3-4 sentence summary names the top requirements the candidate can back up and includes
    one result with a number taken from an achievement;
  * skills use the posting's wording, most important first, and unrelated skills are left out;
  * within each role the most relevant bullets come first; weak or irrelevant ones are dropped;
  * education and certifications close the page.

Hard rules: nothing is invented. Every line points at profile records; titles, employers and
dates are copied unchanged; rewording is limited to stored variants that passed the fact check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.core.dates import format_month, format_range
from app.core.taxonomy import get_taxonomy
from app.core.text import word_count
from app.ingest.claims import AWKWARD_PATTERNS, PRODUCTION_RE
from app.matching.engine import EvidenceIndex, achievement_relevance, assess_skill, professional_months
from app.schemas.common import ClaimFlag, stable_id
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport
from app.schemas.profile import Achievement, CandidateProfile, Project, Role
from app.schemas.resume import (
    CertificationLine,
    ChangeLogEntry,
    EducationLine,
    ExperienceEntry,
    LayoutSettings,
    OmittedItem,
    ProjectEntry,
    ResumeBullet,
    ResumeHeader,
    SkillLine,
    SummarySentence,
    TailoredResume,
)
from app.tailoring.style import ai_tells

SKILL_GROUP_ORDER = ["language", "genai", "ml", "data_eng", "database", "analytics", "cloud", "business", "marketing"]
SKILL_GROUP_LABELS = {
    "language": "Languages", "genai": "LLMs & GenAI", "ml": "Machine Learning", "data_eng": "Data Engineering",
    "database": "Databases", "analytics": "Data & Analytics", "cloud": "Cloud & DevOps", "business": "Process & Tools",
    "marketing": "Marketing Analytics", "concept": "Other",
}
# Derived competencies that read oddly in a skills list unless the posting asks for them.
LIST_ONLY_IF_REQUESTED = {"Inventory Management", "Operations Analytics", "Stakeholder Management", "Real-Time Reporting",
                          "Technical Documentation", "Production Deployment", "Reliability Engineering",
                          "Distributed Systems", "Container Deployment", "Data Engineering", "Structured Outputs",
                          "Context Engineering", "Monitoring", "Credit Risk Modeling", "Text Classification",
                          "Experiment Tracking", "Data Pipelines", "Information Retrieval", "Window Functions",
                          "Query Optimization"}


# Broad fields; fine in the skills list, too vague for "Skilled in ..." in the summary.
GENERIC_FOR_SUMMARY = {"Machine Learning", "Data Analysis", "Data Pipelines", "Data Engineering", "Statistics",
                       "Deep Learning", "Generative AI", "Containerization", "Cloud Platforms", "KPI Reporting",
                       "Data Visualization", "Business Intelligence", "Information Retrieval"}
# Derived (bullet-only) competencies that are never listed as skills; they belong in bullets.
NEVER_LIST_DERIVED = {"Stakeholder Management", "Operations Analytics", "Inventory Management", "Technical Documentation",
                      "Real-Time Reporting", "Production Deployment", "Reliability Engineering", "Container Deployment",
                      "Structured Outputs", "Context Engineering", "Credit Risk Modeling", "Text Classification",
                      "Monitoring", "Distributed Systems", "Experiment Tracking", "Data Engineering"}
PROPER_CATEGORIES = {"language", "cloud", "database"}
# Skill families a recruiter reads as neighbours (an analyst posting values ETL and data quality).
ADJACENT_CATEGORIES = {"data_eng": {"analytics", "database", "cloud"}, "database": {"analytics", "data_eng"},
                       "analytics": {"data_eng", "database", "ml"}, "ml": {"analytics", "genai"}, "genai": {"ml"},
                       "cloud": {"data_eng", "genai", "ml"}}
# When fewer skills than this relate to the posting, a few evidenced neighbours fill out the section.
THIN_SKILLS = 11
MAX_ADJACENT_SKILLS = 5


def summary_display(canonical: str, written: str) -> str:
    """Lower-case concept names inside a sentence; keep product names and acronyms."""
    tax = get_taxonomy()
    node = tax.nodes.get(canonical)
    text = written if not written.islower() else canonical
    if canonical == "Large Language Models":
        return "LLMs"
    is_concept = canonical in GENERIC_FOR_SUMMARY or (node and node.category in ("concept", "business", "soft")) \
        or (node and node.category in ("data_eng", "analytics", "ml", "genai") and " " in canonical
            and not any(any(c.isupper() for c in w[1:]) for w in canonical.split())
            and canonical not in ("Power BI", "Hugging Face", "Apache Airflow", "Apache Spark", "Apache Kafka"))
    if is_concept:
        return " ".join(w if (w.isupper() and len(w) > 1) or any(c.isupper() for c in w[1:]) else w.lower()
                        for w in text.split())
    return text


@dataclass
class TailorOptions:
    page_target: int | None = None  # None: 1 page for early-career, else 2
    max_bullets_per_role: int = 5
    max_projects: int = 3
    max_bullets_per_project: int = 2
    use_unapproved_wording: bool = True  # drafts may use pending wording; it is flagged for approval
    font_family: str | None = None  # "sans" | "serif"; default follows the source resume
    today: date | None = None


@dataclass
class TailorResult:
    resume: TailoredResume
    change_log: list[ChangeLogEntry]
    relevance: dict[str, tuple[float, list[str]]]
    # Content left out only for space; the page fitter may add it back if the page has room.
    reserve_projects: list[ProjectEntry] = field(default_factory=list)
    reserve_bullets: list[tuple[str, ResumeBullet]] = field(default_factory=list)  # (role_id, bullet)


# --------------------------------------------------------------------------- helpers

def clean_target_title(title: str) -> str:
    t = re.sub(r"\s*[\(\[]?(remote|hybrid|on-?site|contract|full[- ]time|part[- ]time)[\)\]]?\s*$", "", title, flags=re.I)
    t = re.sub(r"\s*[-–|,]\s*$", "", t)
    return t.strip() or title.strip()


def _base_title(title: str) -> str:
    base = re.split(r"\s+[-–(|,]\s*|\s+\(", title)[0]
    return re.sub(r"\s+(I|II|III|IV|V|\d)$", "", base).strip()


def _lower_title(title: str) -> str:
    words = []
    for w in title.split():
        words.append(w if (w.isupper() and len(w) <= 4) or any(c.isupper() for c in w[1:]) else w.lower())
    return " ".join(words)


def _fix_case(text: str) -> str:
    """'Master's in Engineering science' -> 'Master's in Engineering Science' (formatting only)."""
    small = {"of", "in", "and", "the", "for", "with", "on", "at", "to", "a", "an"}
    out = []
    for i, w in enumerate(text.split(" ")):
        if i > 0 and w.lower() in small:
            out.append(w.lower())
        elif w[:1].islower() and w.isalpha():
            out.append(w[:1].upper() + w[1:])
        else:
            out.append(w)
    return " ".join(out).rstrip(".")


def _project_topic(name: str) -> str:
    """'Retrieval-Augmented Conversational AI Systems' -> 'retrieval-augmented conversational AI'."""
    name = re.sub(r"\s+(systems?|project|application|app|platform)$", "", name.strip(), flags=re.I)
    out = []
    for w in name.split():
        parts = []
        for part in w.split("-"):
            keep = (part.isupper() and len(part) > 1) or any(c.isupper() for c in part[1:])
            parts.append(part if keep else part.lower())
        out.append("-".join(parts))
    return " ".join(out)


def _years_phrase(months: int) -> str | None:
    if months < 6:
        return None
    if months < 12:
        return f"{months} months"
    if months < 24:
        return "over a year"
    return f"{months // 12}+ years"


def _job_skill_weights(job: JobAnalysis) -> dict[str, float]:
    return {s.canonical: s.importance for s in job.skill_importance}


def _text_relevance(text: str, weights: dict[str, float]) -> float:
    tax = get_taxonomy()
    found = set()
    for name in tax.find_canonical(text):
        found.add(name)
        found |= set(tax.ancestors(name))
    return sum(w for k, w in weights.items() if k in found)


def _wording_quality(text: str, *, academic: bool) -> tuple[float, list[ClaimFlag]]:
    score, flags = 0.0, []
    n = word_count(text)
    if 14 <= n <= 28:
        score += 0.15
    elif n < 10:
        score -= 0.3
    elif n > 32:
        score -= 0.1 * ((n - 32) / 8 + 1)
    for phrase, why in ai_tells(text):
        score -= 0.25
        flags.append(ClaimFlag(kind="grammar", span=phrase, message=f"Reads as generated text: {why}", severity="info"))
    for rx, msg in AWKWARD_PATTERNS:
        if rx.search(text):
            score -= 0.3
            flags.append(ClaimFlag(kind="grammar", span=rx.search(text).group(0), message=msg, severity="info"))
    if academic:
        for m in PRODUCTION_RE.finditer(text):
            score -= 1.5
            flags.append(ClaimFlag(kind="academic_vs_production", span=m.group(0),
                                   message=f"'{m.group(0)}' implies production use in an academic project.",
                                   severity="critical"))
    return score, flags


@dataclass
class Choice:
    text: str
    variant_id: str | None
    origin: str
    approved: bool
    score: float
    flags: list[ClaimFlag]


def choose_wording(ach: Achievement, parent: Role | Project, weights: dict[str, float],
                   allow_unapproved: bool) -> Choice:
    academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
    options: list[Choice] = []
    base_q, base_flags = _wording_quality(ach.text, academic=academic)
    is_original = ach.text == ach.original_text
    # Wording is chosen mainly on quality and approval; relevance only breaks ties, so a clumsy
    # sentence never wins just because it repeats more keywords.
    options.append(Choice(ach.text, None, "original" if is_original else "user", True,
                          _text_relevance(ach.text, weights) * 0.2 + base_q * 1.5 + (0.0 if is_original else 0.6),
                          base_flags))
    for v in ach.variants:
        if v.fact_check is not None and not v.fact_check.passed:
            continue
        if not v.approved and not allow_unapproved:
            continue
        q, flags = _wording_quality(v.text, academic=academic)
        bonus = {"user": 0.45, "assistant": 0.25, "llm": 0.2, "rule_cleanup": 0.1}.get(v.origin, 0.0)
        if v.approved:
            bonus += 0.25
        emphasis = sum(weights.get(e, 0.0) for e in v.emphasis) * 0.3
        if "summary" in v.emphasis:
            bonus -= 0.6  # short summary-only phrasing, not meant as a bullet
        options.append(Choice(v.text, v.id, v.origin, v.approved,
                              _text_relevance(v.text, weights) * 0.2 + q * 1.5 + bonus + emphasis, flags))
    options.sort(key=lambda c: (-round(c.score, 6), c.variant_id or ""))
    best = options[0]
    # Consistent end punctuation is formatting, not rewording.
    if best.text and not best.text.rstrip().endswith((".", "!", "?")):
        best = Choice(best.text.rstrip() + ".", best.variant_id, best.origin, best.approved, best.score, best.flags)
    return best


# --------------------------------------------------------------------------- skills

def _display_case(display: str, canonical: str) -> str:
    """Tidy inconsistent casing from the source ('Natural Language processing') without changing words."""
    words = display.split()
    if len(words) > 1 and any(w[:1].isupper() for w in words) and any(w[:1].islower() for w in words):
        return " ".join(w if not w[:1].islower() or w in ("and", "of", "for") else w[:1].upper() + w[1:] for w in words)
    if display.islower() and display.lower() != canonical.lower():
        return display[:1].upper() + display[1:]
    if display.islower():
        return canonical
    return display


# Where a one-item or surplus skill group goes: the closest family already on the resume.
GROUP_NEIGHBOURS = {"data_eng": ["analytics", "database", "cloud"], "database": ["data_eng", "analytics", "cloud"],
                    "analytics": ["data_eng", "ml"], "ml": ["genai", "analytics"], "genai": ["ml"],
                    "cloud": [], "language": []}


def fold_skill_groups(groups: dict[str, list], order: list[str], max_lines: int = 5) -> None:
    """Fold one-item groups (and anything beyond ``max_lines``) into the closest neighbouring group, in place.

    Groups with no neighbour on the resume end up together on a final "Tools" line.
    """
    def fold(cat: str) -> bool:
        for target in GROUP_NEIGHBOURS.get(cat, []):
            if target in groups and target != cat:
                groups[target].extend(groups.pop(cat))
                order.remove(cat)
                return True
        return False

    for cat in list(order):
        if cat in groups and len(groups[cat]) == 1 and cat != "language" and len(order) > 3:
            fold(cat)
    while len(order) > max_lines:
        movable = [c for c in order if c not in ("language", "tools")]
        if not movable:
            break
        smallest = min(movable, key=lambda c: (len(groups[c]), -order.index(c)))
        if not fold(smallest):
            groups.setdefault("tools", []).extend(groups.pop(smallest))
            order.remove(smallest)
            if "tools" not in order:
                order.append("tools")


def build_skills(profile: CandidateProfile, job: JobAnalysis, idx: EvidenceIndex,
                 max_items: int = 24) -> tuple[list[SkillLine], list[OmittedItem], list[str]]:
    tax = get_taxonomy()
    jd = {s.canonical: s for s in job.skill_importance}
    candidates: dict[str, dict] = {}
    for s in profile.skills:
        if s.verification == "rejected":
            continue
        if s.derived_from_bullets and s.name in NEVER_LIST_DERIVED:
            # Not listed under its own (awkward) name, but it can justify the posting's broader term
            # (built real-time KPI dashboards -> "Dashboards").
            for req, rs in jd.items():
                node = tax.nodes.get(req)
                if (tax.relationship(s.name, req).relation == "specific_satisfies_generic" and node
                        and node.category not in ("soft", "business", "concept") and not node.family
                        and req not in candidates and rs.importance >= 0.2):
                    candidates[req] = {"display": req, "ids": [s.id], "listed": False, "evidence": True}
            continue
        candidates.setdefault(s.name, {"display": _display_case(s.display, s.name), "ids": [s.id],
                                       "listed": not s.derived_from_bullets,
                                       "evidence": bool(s.evidence_achievement_ids)})
    scored: list[tuple[float, str, str]] = []
    adjacent: list[tuple[float, str, str]] = []
    omitted: list[OmittedItem] = []
    for name, info in candidates.items():
        best = 0.0
        display = info["display"]
        for req, rs in jd.items():
            rel = tax.relationship(name, req).relation
            if rel == "exact":
                if rs.importance > best:
                    best = rs.importance
                # Mirror the posting's wording only when it names exactly this skill ("scikit-learn",
                # "Postgres"); never when it bundles more ("ETL/ELT").
                if tax.find_canonical(rs.as_written) == [name] and rs.as_written.lower() != name.lower() \
                        and rs.as_written.lower() != display.lower():
                    display = rs.as_written
            elif rel == "specific_satisfies_generic" and info["listed"]:
                best = max(best, rs.importance * 0.8)
            elif rel == "sibling":
                best = max(best, rs.importance * 0.15)
        cat = tax.category(name) or "concept"
        if cat == "soft" or (name in LIST_ONLY_IF_REQUESTED and best < 0.2 and not info["listed"]):
            continue
        if best == 0.0:
            cat_weight = max((rs.importance for rs in jd.values() if tax.category(rs.canonical) == cat), default=0.0)
            best = 0.05 * cat_weight if info["listed"] else 0.0
        if best <= 0.02:
            neighbours_w = [max((rs.importance for rs in jd.values() if tax.category(rs.canonical) == c), default=0.0)
                            for c in ADJACENT_CATEGORIES.get(cat, ())]
            if cat not in ("concept", "business") and (info["listed"] or info["evidence"]) and any(neighbours_w):
                # Ranked below every skill the posting relates to: evidenced and listed first.
                weight = (1.0 if info["listed"] and info["evidence"] else 0.8 if info["evidence"] else 0.6)
                adjacent.append((0.019 * weight * sum(neighbours_w) / 3, name, display))
            else:
                omitted.append(OmittedItem(item_type="skill", item_id=info["ids"][0], text=info["display"],
                                           reason="Not relevant to this posting"))
            continue
        scored.append((best + (0.05 if info["evidence"] else 0.0), name, display))
    scored.sort(key=lambda t: (-t[0], t[1]))
    # A bullet-derived broad concept adds nothing when a listed, more specific skill covers it
    # (derived "Containerization" next to listed "Docker").
    names = {n for _s, n, _d in scored}
    pruned = []
    for sc, name, display in scored:
        if not candidates[name]["listed"] and any(
                other != name and name in tax.ancestors(other) and candidates[other]["listed"] for other in names):
            omitted.append(OmittedItem(item_type="skill", item_id=candidates[name]["ids"][0], text=display,
                                       reason="Covered by a more specific skill already listed"))
            continue
        pruned.append((sc, name, display))
    adjacent.sort(key=lambda t: (-t[0], t[1]))
    room = min(MAX_ADJACENT_SKILLS, max(0, THIN_SKILLS - len(pruned)))
    pruned.extend(adjacent[:room])  # scored below every related skill, so the order holds
    for _sc, name, display in adjacent[room:]:
        omitted.append(OmittedItem(item_type="skill", item_id=candidates[name]["ids"][0], text=display,
                                   reason="Not relevant to this posting"))
    kept, dropped = pruned[:max_items], pruned[max_items:]
    for _sc, name, display in dropped:
        omitted.append(OmittedItem(item_type="skill", item_id=candidates[name]["ids"][0], text=display,
                                   reason="Lower priority for this posting (space)"))
    groups: dict[str, list[tuple[float, str, str]]] = {}
    for sc, name, display in kept:
        cat = tax.category(name) or "concept"
        if cat in ("concept", "business", "marketing"):
            cat = "analytics" if cat != "concept" else "ml"
        groups.setdefault(cat, []).append((sc, name, display))
    order = sorted(groups, key=lambda c: (-max(x[0] for x in groups[c]),
                                          SKILL_GROUP_ORDER.index(c) if c in SKILL_GROUP_ORDER else 99))
    if "language" in order and order.index("language") > 0:
        order.remove("language")
        order.insert(0, "language")
    fold_skill_groups(groups, order)
    lines = []
    for cat in order:
        label = SKILL_GROUP_LABELS.get(cat, "Tools")
        items = sorted(groups[cat], key=lambda t: (-t[0], t[1]))
        seen_disp: list[str] = []
        sources: dict[str, list[str]] = {}
        for _sc, name, display in items:
            if display.lower() in (d.lower() for d in seen_disp) or display.lower() == label.lower():
                continue
            seen_disp.append(display)
            sources[display] = candidates[name]["ids"]
        if seen_disp:
            lines.append(SkillLine(category=label, items=seen_disp, sources=sources))

    top_for_summary = []
    for rs in job.skill_importance:
        node = tax.nodes.get(rs.canonical)
        if node is None or node.family or node.category in ("soft", "business", "concept") \
                or rs.canonical in NEVER_LIST_DERIVED \
                or any(tax.category(p) == "language" for p in node.parents):  # say "SQL", not "window functions"
            continue
        a = assess_skill(rs.canonical, idx)
        if a.level not in ("direct", "partial"):
            continue
        score = rs.importance * (1.0 if a.level == "direct" else 0.8)
        score *= 0.45 if rs.canonical in GENERIC_FOR_SUMMARY else 1.0
        score += 0.25 if (rs.in_mandatory or rs.in_title) else 0.0
        shown = rs.canonical
        written = rs.as_written
        # Prefer the specific skill that earned the match when the posting also names it (LLM -> RAG).
        if rs.canonical in GENERIC_FOR_SUMMARY | {"Large Language Models"}:
            # Name the specific skill that earned the match when the posting also asks for it (LLMs -> RAG).
            specifics = sorted((x for x in jd.values() if rs.canonical in tax.ancestors(x.canonical)
                                and assess_skill(x.canonical, idx).level == "direct"),
                               key=lambda x: (-x.importance, x.canonical))
            if specifics:
                shown, written = specifics[0].canonical, specifics[0].as_written
        top_for_summary.append((-round(score, 6), written, shown))
    top_for_summary.sort()
    picked: list[str] = []
    picked_canon: list[str] = []
    for _score, written, canon in top_for_summary:
        if canon in picked_canon or any(
                tax.relationship(canon, p).relation == "specific_satisfies_generic" or
                tax.relationship(p, canon).relation == "specific_satisfies_generic" for p in picked_canon):
            continue
        picked.append(summary_display(canon, written))
        picked_canon.append(canon)
        if len(picked) == 3:
            break
    return lines, omitted, picked


# --------------------------------------------------------------------------- summary

def build_summary(profile: CandidateProfile, job: JobAnalysis, target_title: str, top_skills: list[str],
                  relevance: dict[str, tuple[float, list[str]]], chosen: dict[str, Choice],
                  projects_used: list[Project], today: date | None) -> list[SummarySentence]:
    sentences: list[SummarySentence] = []
    roles = sorted([r for r in profile.roles if r.verification != "rejected"], key=lambda r: r.start or "", reverse=True)
    months = professional_months(profile, today)
    edu = sorted([e for e in profile.education if e.verification != "rejected"],
                 key=lambda e: ({"doctorate": 4, "master": 3, "bachelor": 2}.get(e.level, 0), e.end or ""), reverse=True)
    identity = _base_title(target_title)
    parts, ids = [], []
    if edu and edu[0].level in ("master", "doctorate"):
        degree = _fix_case(edu[0].degree)
        parts.append(f"a {degree}")
        ids.append(edu[0].id)
    yp = _years_phrase(months)
    if roles and yp:
        r = roles[0]
        role_base = _base_title(r.title)
        same_family = role_base.lower() == identity.lower()
        org = r.organization
        org_phrase = f"the {org}" if re.match(r"^(University|Institute|College)\b", org) else org
        if same_family:
            parts.insert(0, f"{yp} of hands-on experience at {org_phrase}")
        else:
            parts.append(f"{yp} as a {_lower_title(role_base)} at {org_phrase}")
        ids.extend(r.id for r in roles[:1])
    if parts:
        sentences.append(SummarySentence(text=f"{identity} with {' and '.join(parts)}.", kind="identity", source_ids=ids))
    else:
        sentences.append(SummarySentence(text=f"{identity} focused on {', '.join(top_skills[:2]) or 'practical work'}.",
                                         kind="identity", source_ids=ids))
    if top_skills:
        skills_txt = top_skills[0] if len(top_skills) == 1 else ", ".join(top_skills[:-1]) + f" and {top_skills[-1]}"
        tail = ""
        topics = [_project_topic(p.name) for p in projects_used[:2]]
        if topics:
            kind = "academic projects" if all(p.context == "academic" for p in projects_used[:2]) else "projects"
            tail = f", with {kind} in {' and '.join(topics)}"
        sentences.append(SummarySentence(text=f"Skilled in {skills_txt}{tail}.", kind="skills",
                                         source_ids=[p.id for p in projects_used[:2]]))
    # One result with a number, from the most relevant achievement that has one.
    best = None
    for ach, parent in profile.usable_achievements():
        if not ach.metrics or ach.id not in chosen:
            continue
        rel = relevance.get(ach.id, (0.0, []))[0]
        pro_bonus = 0.3 if isinstance(parent, Role) else 0.0
        ver_bonus = 0.2 if ach.verification in ("verified", "user_corrected") else 0.0
        short = [v for v in ach.variants if "summary" in v.emphasis and (v.fact_check is None or v.fact_check.passed)]
        text = short[0].text if short else chosen[ach.id].text
        if word_count(text) > 26:
            continue
        academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
        quality, qflags = _wording_quality(text, academic=academic)
        if any(f.severity == "critical" for f in qflags):
            continue
        score = rel + pro_bonus + ver_bonus + quality + (0.4 if short else 0.0)
        if best is None or score > best[0]:
            best = (score, ach, text)
    if best:
        _s, ach, text = best
        sentences.append(SummarySentence(text=text.rstrip(".") + ".", kind="result", source_ids=[ach.id]))
    return sentences


# --------------------------------------------------------------------------- main

def tailor(profile: CandidateProfile, job: JobAnalysis, report: MatchReport | None = None,
           options: TailorOptions | None = None, *, source_fonts: list[str] | None = None,
           variant: str | None = None) -> TailorResult:
    options = options or TailorOptions()
    weights = _job_skill_weights(job)
    relevance = achievement_relevance(profile, job)
    idx = EvidenceIndex.build(profile)
    change_log: list[ChangeLogEntry] = []
    omitted: list[OmittedItem] = []

    target_title = clean_target_title(job.title) or "Professional"
    change_log.append(ChangeLogEntry(kind="title", target="header", before=None, after=target_title,
                                     reason="The posting's exact title goes directly under the name so the recruiter "
                                            "sees the match first. It names the role applied for, not a past title."))

    # ---- experience (chronology preserved; bullets ordered by relevance) --------
    experience: list[ExperienceEntry] = []
    chosen: dict[str, Choice] = {}
    reserve_bullets: list[tuple[str, ResumeBullet]] = []
    roles = sorted([r for r in profile.roles if r.verification != "rejected"],
                   key=lambda r: (r.end == "present", r.end or "", r.start or ""), reverse=True)
    for r in roles:
        achs = [a for a in r.achievements if a.verification != "rejected" and a.allowed_usage != "do_not_use"]
        ordered = sorted(achs, key=lambda a: (-relevance.get(a.id, (0, []))[0], r.achievements.index(a)))
        keep = ordered[: options.max_bullets_per_role]
        # Drop clearly irrelevant bullets as long as at least three stay.
        while len(keep) > 3 and relevance.get(keep[-1].id, (0, []))[0] < 0.12:
            dropped = keep.pop()
            omitted.append(OmittedItem(item_type="bullet", item_id=dropped.id, text=dropped.text,
                                       reason="Not relevant to this posting"))
        for a in ordered[len(keep):]:
            if a.id not in {o.item_id for o in omitted}:
                omitted.append(OmittedItem(item_type="bullet", item_id=a.id, text=a.text, reason="Space; lower relevance"))
            # Kept in reserve: the fitter restores it, most relevant first, only into free space
            # (a one-page resume with a blank quarter reads thin).
            c = choose_wording(a, r, weights, options.use_unapproved_wording)
            rel, hits = relevance.get(a.id, (0.0, []))
            reserve_bullets.append((r.id, ResumeBullet(
                id=stable_id("b", a.id, c.variant_id or "orig"), text=c.text, achievement_ids=[a.id],
                variant_id=c.variant_id, origin=c.origin, approved=c.approved, relevance=rel,  # type: ignore[arg-type]
                matched_requirements=hits, flags=c.flags)))
        bullets = []
        for a in keep:
            c = choose_wording(a, r, weights, options.use_unapproved_wording)
            chosen[a.id] = c
            rel, hits = relevance.get(a.id, (0.0, []))
            bullets.append(ResumeBullet(id=stable_id("b", a.id, c.variant_id or "orig"), text=c.text, achievement_ids=[a.id],
                                        variant_id=c.variant_id, origin=c.origin, approved=c.approved, relevance=rel,  # type: ignore[arg-type]
                                        matched_requirements=hits, flags=c.flags))
        experience.append(ExperienceEntry(role_id=r.id, title=r.title, organization=r.organization, location=r.location,
                                          date_range=format_range(r.start, r.end) or r.date_text, bullets=bullets))

    # ---- projects (most relevant first) -----------------------------------------
    proj_scores = []
    for p in profile.projects:
        if p.verification == "rejected":
            continue
        rels = sorted((relevance.get(a.id, (0, []))[0] for a in p.achievements
                       if a.verification != "rejected" and a.allowed_usage != "do_not_use"), reverse=True)
        if not rels:
            continue
        proj_scores.append((rels[0] + 0.3 * (rels[1] if len(rels) > 1 else 0), p))
    proj_scores.sort(key=lambda t: (-t[0], profile.projects.index(t[1])))
    projects: list[ProjectEntry] = []
    used_projects: list[Project] = []
    reserve_projects: list[ProjectEntry] = []

    def project_entry(p: Project, max_bullets: int) -> ProjectEntry:
        achs = [a for a in p.achievements if a.verification != "rejected" and a.allowed_usage != "do_not_use"]
        ordered = sorted(achs, key=lambda a: (-relevance.get(a.id, (0, []))[0], p.achievements.index(a)))
        keep = ordered[:max_bullets]
        for a in ordered[len(keep):]:
            omitted.append(OmittedItem(item_type="bullet", item_id=a.id, text=a.text, reason="Space; lower relevance"))
        bullets = []
        for a in keep:
            c = choose_wording(a, p, weights, options.use_unapproved_wording)
            chosen[a.id] = c
            rel, hits = relevance.get(a.id, (0.0, []))
            bullets.append(ResumeBullet(id=stable_id("b", a.id, c.variant_id or "orig"), text=c.text, achievement_ids=[a.id],
                                        variant_id=c.variant_id, origin=c.origin, approved=c.approved, relevance=rel,  # type: ignore[arg-type]
                                        matched_requirements=hits, flags=c.flags))
        descriptor = {"academic": "Academic project", "personal": "Personal project",
                      "open_source": "Open-source project"}.get(p.context)
        return ProjectEntry(project_id=p.id, name=p.name, descriptor=descriptor,
                            technologies=[t for t in p.technologies if t in weights][:5],
                            date_range=p.date_text, bullets=bullets)

    for score, p in proj_scores:
        if len(projects) >= options.max_projects or (score < 0.15 and len(projects) >= 1):
            omitted.append(OmittedItem(item_type="project", item_id=p.id, text=p.name, reason="Less relevant to this posting"))
            change_log.append(ChangeLogEntry(kind="project_removed", target=p.name, before=p.name, after=None,
                                             reason="Less relevant to this posting than the projects kept."))
            reserve_projects.append(project_entry(p, 2))
            continue
        projects.append(project_entry(p, options.max_bullets_per_project))
        used_projects.append(p)

    # ---- skills ---------------------------------------------------------------
    skill_lines, skill_omitted, top_skills = build_skills(profile, job, idx)
    omitted.extend(skill_omitted)
    original_skill_order = [s.display for s in profile.skills if not s.derived_from_bullets]
    new_skill_order = [i for line in skill_lines for i in line.items]
    change_log.append(ChangeLogEntry(kind="skills_reordered", target="skills",
                                     before=", ".join(original_skill_order), after=", ".join(new_skill_order),
                                     reason="Skills follow the posting's order of importance and wording; unrelated "
                                            "skills are left out to keep the match obvious."))
    for o in skill_omitted:
        change_log.append(ChangeLogEntry(kind="skill_removed", target=o.text, before=o.text, after=None, reason=o.reason,
                                         evidence_ids=[o.item_id]))

    # ---- summary --------------------------------------------------------------
    summary = build_summary(profile, job, target_title, top_skills, relevance, chosen, used_projects, options.today)
    change_log.append(ChangeLogEntry(kind="summary", target="summary", before=profile.original_summary,
                                     after=" ".join(s.text for s in summary),
                                     reason="3-4 sentence summary naming the posting's top requirements you can back up, "
                                            "with one measured result taken from your achievements.",
                                     evidence_ids=[i for s in summary for i in s.source_ids]))

    # ---- education & certifications ------------------------------------------
    education = [EducationLine(education_id=e.id, degree=_fix_case(e.degree), institution=e.institution,
                               location=e.location, date=(f"Expected {format_month(e.end)}" if e.status == "expected"
                                                          else format_month(e.end)) or e.date_text, gpa=e.gpa)
                 for e in sorted([e for e in profile.education if e.verification != "rejected"],
                                 key=lambda e: e.end or "", reverse=True)]
    certs = []
    for c in profile.certifications:
        if c.verification == "rejected":
            continue
        rel = _text_relevance(f"{c.name} {c.detail or ''}", weights)
        certs.append((rel, c))
    certs.sort(key=lambda t: (-t[0], -(int((t[1].date or "0000-00").replace("-", "")))))
    certifications = [CertificationLine(certification_id=c.id, name=c.name, detail=c.detail,
                                        date=format_month(c.date) or c.date_text) for _r, c in certs]

    # ---- wording changes for the log ------------------------------------------
    for entry in experience:
        role = next(r for r in profile.roles if r.id == entry.role_id)
        _log_bullets(change_log, entry.bullets, role.achievements, f"{entry.title}, {entry.organization}")
    for pe in projects:
        proj = next(p for p in profile.projects if p.id == pe.project_id)
        _log_bullets(change_log, pe.bullets, proj.achievements, pe.name)
    for o in omitted:
        if o.item_type == "bullet":
            change_log.append(ChangeLogEntry(kind="bullet_removed", target=o.item_id, before=o.text, after=None,
                                             reason=o.reason, evidence_ids=[o.item_id]))

    # ---- section order -----------------------------------------------------------
    section_order = ["summary", "skills", "experience", "projects", "education", "certifications"]
    best_role = max((b.relevance for e in experience for b in e.bullets), default=0.0)
    best_proj = max((b.relevance for p in projects for b in p.bullets), default=0.0)
    if projects and experience and best_proj - best_role >= 0.35 and best_role < 0.5:
        section_order = ["summary", "skills", "projects", "experience", "education", "certifications"]
        change_log.append(ChangeLogEntry(kind="section_reordered", target="sections", before="Experience, Projects",
                                         after="Projects, Experience",
                                         reason="Your projects match this posting much more closely than your work "
                                                "history, so they appear first."))

    years = professional_months(profile, options.today) / 12
    page_target = options.page_target or (1 if years < 5 else 2)
    font = options.font_family or _font_from_source(source_fonts)
    contact = _contact(profile)
    resume = TailoredResume(
        header=ResumeHeader(name=profile.personal.name, target_title=target_title, contact=contact[0], links=contact[1]),
        summary=summary, skills=skill_lines, experience=experience, projects=projects, education=education,
        certifications=certifications, section_order=section_order,
        layout=LayoutSettings(page_target=page_target, font_family=font),  # type: ignore[arg-type]
        omitted=omitted, gaps=report.missing_mandatory if report else [],
        top_requirements=top_skills, variant=variant,
    )
    return TailorResult(resume=resume, change_log=change_log, relevance=relevance,
                        reserve_projects=reserve_projects, reserve_bullets=reserve_bullets)


def _log_bullets(log: list[ChangeLogEntry], bullets: list[ResumeBullet], source: list[Achievement], where: str) -> None:
    for pos, b in enumerate(bullets):
        ach = next(a for a in source if a.id == b.achievement_ids[0])
        if b.text.strip().rstrip(".") != ach.original_text.strip().rstrip("."):
            log.append(ChangeLogEntry(
                kind="bullet_reworded", target=b.id, before=ach.original_text, after=b.text,
                reason=f"[{where}] Wording from a {b.origin.replace('_', ' ')} variant that passed the fact check"
                       + ("" if b.approved else "; waiting for your approval"),
                evidence_ids=b.achievement_ids, requires_approval=not b.approved))
        orig_pos = source.index(ach)
        if orig_pos != pos:
            log.append(ChangeLogEntry(kind="bullet_reordered", target=b.id, before=f"position {orig_pos + 1}",
                                      after=f"position {pos + 1}",
                                      reason=f"[{where}] More relevant bullets first.", evidence_ids=b.achievement_ids))


def _font_from_source(fonts: list[str] | None) -> str:
    if fonts and any(re.search(r"times|garamond|georgia|cambria|serif", f, re.I) for f in fonts):
        return "serif"
    return "sans"


def _contact(profile: CandidateProfile) -> tuple[list[str], list[str]]:
    p = profile.personal
    items, links = [], []
    if p.email:
        items.append(p.email)
        links.append(f"mailto:{p.email}")
    if p.phone:
        items.append(_format_phone(p.phone))
        links.append("")
    for lk in p.links:
        disp = re.sub(r"^https?://(www\.)?", "", lk.url).rstrip("/")
        items.append(disp)
        links.append(lk.url if lk.url.startswith("http") else f"https://{lk.url}")
    if p.location:
        items.append(p.location)
        links.append("")
    return items, links


def _format_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 {digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[0:3]}-{digits[3:6]}-{digits[6:]}"
    return phone
