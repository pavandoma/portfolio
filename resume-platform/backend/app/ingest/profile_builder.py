"""Build a CandidateProfile (with evidence records and review issues) from a parsed resume."""

from __future__ import annotations

import re
from datetime import date

from app.core.dates import is_past
from app.core.taxonomy import get_taxonomy
from app.core.text import collapse_ws, normalize_key
from app.ingest.claims import analyse_claims, extract_metrics, split_skills
from app.ingest.resume_parser import ParsedEntry, ParsedResume, smart_title
from app.schemas.common import SourceRef, stable_id
from app.schemas.profile import (
    Achievement,
    CandidateProfile,
    Certification,
    Education,
    Link,
    PersonalInfo,
    PhrasingVariant,
    ProfileIssue,
    Project,
    Role,
    Skill,
)
from app.tailoring.rewrite import fact_check, rule_cleanup

_DEGREE_LEVELS = [
    (re.compile(r"ph\.?\s?d|doctor", re.I), "doctorate"),
    (re.compile(r"master|m\.?\s?s\b|m\.?\s?tech|m\.?eng|mba|m\.?sc|engineering science", re.I), "master"),
    (re.compile(r"bachelor|b\.?\s?tech|b\.?\s?s\b|b\.?\s?e\b|b\.?eng|b\.?sc|b\.?a\b", re.I), "bachelor"),
    (re.compile(r"associate", re.I), "associate"),
    (re.compile(r"diploma|certificate", re.I), "certificate"),
]


def _degree_level(degree: str) -> str:
    for rx, level in _DEGREE_LEVELS:
        if rx.search(degree):
            return level
    return "other"


def _degree_field(degree: str) -> str | None:
    for pattern in (r"\bin\s+(.+)$", r"\bof\s+(.+)$", r"(?:master'?s?|bachelor'?s?)\s+(?:degree\s+)?(.+)$"):
        m = re.search(pattern, degree, re.I)
        if m:
            return m.group(1).strip(" .")
    return None


def _project_context(heading: str | None, entry: ParsedEntry) -> str:
    h = (heading or "").lower()
    descriptors = " ".join(entry.extra.get("descriptors", []) + [entry.extra.get("subtitle") or ""]).lower()
    for text in (h, descriptors):
        if "academic" in text or "course" in text or "university" in text or "capstone" in text or "thesis" in text:
            return "academic"
        if "personal" in text or "side" in text or "hobby" in text:
            return "personal"
        if "open source" in text or "open-source" in text:
            return "open_source"
        if "professional" in text or "client" in text:
            return "professional"
    return "unknown"


def _source(doc_id: str | None, doc_name: str | None, section: str, line: int, page: int, text: str) -> SourceRef:
    return SourceRef(document_id=doc_id, document_name=doc_name, page=page + 1, section=section, line=line,
                     original_text=text)


def _achievement(text: str, parent_id: str, parent_kind: str, context: str | None, src: SourceRef) -> Achievement:
    techs, comps = split_skills(text)
    flags = analyse_claims(text, parent_kind=parent_kind, parent_context=context)
    ach_id = stable_id("ach", parent_id, text)
    allowed = "with_care" if any(f.severity == "critical" for f in flags) else "any"
    ach = Achievement(
        id=ach_id, text=text, original_text=text, source_ref=src, technologies=techs, competencies=comps,
        metrics=extract_metrics(text), flags=flags, evidence_strength="weak", allowed_usage=allowed,
    )
    academic = parent_kind == "project" and context in ("academic", "personal")
    cleaned = rule_cleanup(text, academic=academic)
    if collapse_ws(cleaned.rstrip(".")) != collapse_ws(text.rstrip(".")):
        fc = fact_check(cleaned, [text], academic=academic)
        ach.variants.append(PhrasingVariant(id=stable_id("var", ach_id, cleaned), text=cleaned, origin="rule_cleanup",
                                             approved=False, fact_check=fc))
    return ach


def build_profile(parsed: ParsedResume, *, document_id: str | None = None, document_name: str | None = None,
                  today: date | None = None) -> CandidateProfile:
    tax = get_taxonomy()
    today = today or date.today()
    profile = CandidateProfile()
    if document_id:
        profile.source_document_ids.append(document_id)

    # ---- personal ------------------------------------------------------------
    links = []
    for url in parsed.urls:
        u = url if url.startswith("http") else f"https://{url}"
        label = "LinkedIn" if "linkedin.com" in u else "GitHub" if "github.com" in u else "Website"
        links.append(Link(label=label, url=u))
    name = smart_title(parsed.name) if parsed.name.isupper() else parsed.name
    profile.personal = PersonalInfo(
        name=name, email=parsed.emails[0] if parsed.emails else None,
        phone=parsed.phones[0] if parsed.phones else None, location=parsed.location, links=links,
        source_ref=_source(document_id, document_name, "header", 0, 0, f"{parsed.name}\n{parsed.contact_line}"),
    )
    profile.original_summary = parsed.summary

    # ---- education -------------------------------------------------------------
    for e in parsed.education:
        degree = collapse_ws(e.title or "").rstrip(".")
        status = "unknown"
        if e.end:
            status = "completed" if is_past(e.end, today) else "expected"
        if re.search(r"expected|anticipated", " ".join(e.header), re.I):
            status = "expected"
        profile.education.append(Education(
            id=stable_id("edu", e.organization, degree), institution=e.organization, degree=degree,
            field=_degree_field(degree), level=_degree_level(degree), location=e.location, end=e.end,
            date_text=e.date_text, status=status, gpa=e.extra.get("gpa"),
            source_ref=_source(document_id, document_name, "education", e.line_index, e.page, " | ".join(e.header)),
        ))

    # ---- experience ------------------------------------------------------------
    for e in parsed.experience:
        title = smart_title(e.title) if e.title.isupper() else e.title
        role_id = stable_id("role", e.organization, e.title, e.date_text)
        role = Role(id=role_id, title=title, organization=e.organization, location=e.location, start=e.start,
                    end=e.end, date_text=e.date_text,
                    source_ref=_source(document_id, document_name, "experience", e.line_index, e.page,
                                       " | ".join(e.header)))
        for b in e.bullets:
            src = _source(document_id, document_name, "experience", b.line_index, b.page, b.text)
            role.achievements.append(_achievement(b.text, role_id, "role", None, src))
        profile.roles.append(role)

    # ---- projects --------------------------------------------------------------
    for e in parsed.projects:
        context = _project_context(e.extra.get("section_heading"), e)
        name_txt = smart_title(e.title) if e.title.isupper() else e.title
        subtitle = e.extra.get("subtitle")
        if subtitle and subtitle.isupper():
            subtitle = smart_title(subtitle)
        proj_id = stable_id("proj", e.title)
        links_ = e.extra.get("links", [])
        repo = next((lk for lk in links_ if "github.com" in lk), None)
        project = Project(id=proj_id, name=name_txt, subtitle=subtitle, context=context, date_text=e.date_text,
                          url=e.extra.get("url") or next((lk for lk in links_ if lk != repo), None), repo_url=repo,
                          source_ref=_source(document_id, document_name, "projects", e.line_index, e.page,
                                             " | ".join(e.header)))
        for b in e.bullets:
            src = _source(document_id, document_name, "projects", b.line_index, b.page, b.text)
            project.achievements.append(_achievement(b.text, proj_id, "project", context, src))
        techs: list[str] = []
        for a in project.achievements:
            for t in a.technologies + a.competencies:
                if t not in techs:
                    techs.append(t)
        project.technologies = techs
        profile.projects.append(project)

    # ---- certifications --------------------------------------------------------
    for c in parsed.certifications:
        m = re.match(r"^(?P<n>.+?)\s*\((?P<d>[^()]+)\)\s*$", c.title)
        name_c, detail = (m.group("n"), m.group("d")) if m else (c.title, None)
        issuer = None
        for vendor in ("AWS", "Amazon", "Google", "Microsoft", "Azure", "Anthropic", "Databricks", "Snowflake",
                       "Tableau", "Salesforce", "IBM", "Oracle", "Cisco", "CompTIA", "Coursera", "DeepLearning.AI"):
            # Only when the certificate name starts with the vendor; never guess otherwise.
            if re.match(rf"{re.escape(vendor)}\b", c.title):
                issuer = vendor
                break
        profile.certifications.append(Certification(
            id=stable_id("cert", name_c), name=name_c.strip(), detail=detail, issuer=issuer, date=c.end,
            date_text=c.date_text,
            source_ref=_source(document_id, document_name, "certifications", c.line_index, c.page, c.header[0]),
        ))

    # ---- skills ----------------------------------------------------------------
    seen: dict[str, Skill] = {}
    for row in parsed.skills:
        for item in row["items"]:
            display = item["display"].strip()
            candidates = []
            if item.get("prefix"):
                candidates.append(f"{item['prefix']} {display}")
            candidates.append(display)
            canonical = None
            for cand in candidates:
                canonical = tax.canonical(cand)
                if canonical:
                    break
            name_s = canonical or display
            if name_s in seen:
                continue
            seen[name_s] = Skill(
                id=stable_id("skill", name_s), name=name_s, display=display, category=row["category"],
                taxonomy_category=tax.category(name_s),
                source_ref=_source(document_id, document_name, "skills", row["line_index"], row["page"], row["raw"]),
            )
    # Link skills to the achievements that demonstrate them (including more specific children).
    for ach, _parent in profile.all_achievements():
        mentioned = set(ach.technologies + ach.competencies)
        expanded = set(mentioned)
        for m in mentioned:
            expanded.update(tax.ancestors(m))
        for skill in seen.values():
            if skill.name in expanded:
                skill.evidence_achievement_ids.append(ach.id)
        for m in mentioned:
            if m not in seen and tax.category(m) not in ("soft",):
                seen[m] = Skill(id=stable_id("skill", m), name=m, display=m, category=None,
                                taxonomy_category=tax.category(m), derived_from_bullets=True)
                seen[m].evidence_achievement_ids.append(ach.id)
            elif m in seen and seen[m].derived_from_bullets and ach.id not in seen[m].evidence_achievement_ids:
                seen[m].evidence_achievement_ids.append(ach.id)
    for skill in seen.values():
        skill.self_reported_only = not skill.evidence_achievement_ids
    profile.skills = list(seen.values())

    _infer_employment_types(profile)
    profile.issues = review_issues(profile, today=today)
    return profile


def _infer_employment_types(profile: CandidateProfile) -> None:
    for role in profile.roles:
        org = normalize_key(role.organization)
        for edu in profile.education:
            if org and org in normalize_key(edu.institution) and role.start and edu.end and role.start <= edu.end:
                # Overlaps with study at the same institution. We do not guess the type;
                # we only record it for review (see review_issues).
                role.employment_type = "unknown"


def review_issues(profile: CandidateProfile, *, today: date | None = None) -> list[ProfileIssue]:
    """Questions the candidate should answer before claims are emphasised."""
    issues: list[ProfileIssue] = []
    p = profile.personal
    if not p.email:
        issues.append(ProfileIssue(id="iss-missing-email", kind="missing_field", field="personal.email",
                                   message="No email address found.", severity="critical"))
    if not p.phone:
        issues.append(ProfileIssue(id="iss-missing-phone", kind="missing_field", field="personal.phone",
                                   message="No phone number found.", severity="info"))
    if not p.location:
        issues.append(ProfileIssue(id="iss-missing-location", kind="missing_field", field="personal.location",
                                   message="No city/state in the header. Many recruiters filter by location; add one "
                                           "(e.g. 'Buffalo, NY') if you are comfortable sharing it.",
                                   severity="info"))
    if not any(lk.label == "LinkedIn" for lk in p.links):
        issues.append(ProfileIssue(id="iss-missing-linkedin", kind="missing_field", field="personal.links",
                                   message="No LinkedIn URL found.", severity="info"))
    if not any("github.com" in lk.url for lk in p.links):
        issues.append(ProfileIssue(id="iss-missing-github", kind="missing_field", field="personal.links",
                                   message="No GitHub/portfolio link. Project claims are easier to trust with a repository "
                                           "link; add one as supporting evidence.", severity="info"))
    if profile.work_authorization.status == "unknown":
        issues.append(ProfileIssue(id="iss-work-auth", kind="missing_field", field="work_authorization",
                                   message="Work authorization is unknown. Needed to evaluate postings with sponsorship "
                                           "or citizenship restrictions. It is never printed on the resume.",
                                   severity="info"))
    for role in profile.roles:
        if re.search(r"\b(lead|senior|principal|head|manager|director)\b", role.title, re.I):
            issues.append(ProfileIssue(
                id=stable_id("iss", role.id, "title"), kind="needs_verification", target_id=role.id, field="title",
                message=f"Confirm '{role.title}' is the official title at {role.organization}. Titles are shown exactly "
                        "as confirmed and are never changed to match a posting.", severity="warning"))
        for edu in profile.education:
            if normalize_key(role.organization) and normalize_key(role.organization) in normalize_key(edu.institution):
                issues.append(ProfileIssue(
                    id=stable_id("iss", role.id, "type"), kind="needs_verification", target_id=role.id,
                    field="employment_type",
                    message=f"This role at {role.organization} overlaps your studies there. Confirm whether it was a "
                            "graduate/student position, part-time or full-time; this affects how 'years of "
                            "experience' requirements are evaluated.", severity="warning",
                    options=["student_employment", "part_time", "full_time", "internship"]))
                break
    for ach, parent in profile.all_achievements():
        serious = [f for f in ach.flags if f.severity in ("warning", "critical")]
        if not serious:
            continue
        kinds = sorted({f.kind for f in serious})
        where = parent.name if isinstance(parent, Project) else f"{parent.title}, {parent.organization}"
        issues.append(ProfileIssue(
            id=stable_id("iss", ach.id), kind="needs_verification", target_id=ach.id,
            message=f"[{where}] Confirm: " + "; ".join(f.message for f in serious),
            severity="critical" if any(f.severity == "critical" for f in serious) else "warning",
            options=["verified", "user_corrected", "rejected"], field=",".join(kinds)))
    for skill in profile.skills:
        if skill.self_reported_only and not skill.derived_from_bullets:
            issues.append(ProfileIssue(
                id=stable_id("iss", skill.id), kind="unsupported_claim", target_id=skill.id, field="skill",
                message=f"'{skill.display}' is listed as a skill but no bullet shows it in use. It can stay in the "
                        "skills list, but it will not count as demonstrated experience until you add evidence.",
                severity="info", options=["verified", "rejected"]))
    return issues
