"""Evidence integrity: every statement on the resume must trace to the master profile.

Checks that bullets, summary sentences, skills and the factual entries (employers, titles,
dates, degrees, certifications) point to non-rejected profile records, that rewritten text
passes the fact check against its source, and that employment facts are unchanged.
"""

from __future__ import annotations

from app.core.dates import format_month, format_range
from app.core.taxonomy import get_taxonomy
from app.schemas.profile import CandidateProfile, Project
from app.schemas.resume import TailoredResume
from app.schemas.validation import ClaimTrace, IntegrityReport
from app.tailoring.rewrite import fact_check

VERIFIED = ("verified", "user_corrected")


def _status(verifications: list[str]) -> str:
    if not verifications:
        return "unsupported"
    if any(v == "rejected" for v in verifications):
        return "rejected_source"
    if all(v in VERIFIED for v in verifications):
        return "supported_verified"
    return "supported_unverified"


def check_integrity(profile: CandidateProfile, resume: TailoredResume) -> IntegrityReport:
    claims: list[ClaimTrace] = []
    problems: list[str] = []
    employment_ok = True
    tax = get_taxonomy()

    # Factual entries
    for e in resume.experience:
        role = next((r for r in profile.roles if r.id == e.role_id), None)
        if role is None:
            claims.append(ClaimTrace(location="experience", text=f"{e.title}, {e.organization}", source_ids=[],
                                     status="unsupported", detail="Role not found in profile"))
            employment_ok = False
            continue
        expected_range = format_range(role.start, role.end) or role.date_text
        same = (e.title == role.title and e.organization == role.organization and e.date_range == expected_range
                and (e.location or None) == (role.location or None))
        if not same:
            employment_ok = False
            problems.append(f"Employment facts changed for {role.title} at {role.organization}.")
        claims.append(ClaimTrace(location="experience", text=f"{e.title}, {e.organization}, {e.date_range}",
                                 source_ids=[role.id], status=_status([role.verification]) if same else "unsupported",
                                 detail="" if same else "Title, employer, location or dates differ from the profile"))
        for b in e.bullets:
            claims.append(_bullet_trace(profile, b, "experience", problems))
    for p in resume.projects:
        proj = next((x for x in profile.projects if x.id == p.project_id), None)
        if proj is None or proj.name != p.name:
            claims.append(ClaimTrace(location="projects", text=p.name, source_ids=[], status="unsupported",
                                     detail="Project not found in profile"))
            continue
        for b in p.bullets:
            claims.append(_bullet_trace(profile, b, "projects", problems))
    for ed in resume.education:
        src = next((x for x in profile.education if x.id == ed.education_id), None)
        ok = bool(src and src.institution == ed.institution and src.degree.rstrip(".").lower() == ed.degree.lower())
        claims.append(ClaimTrace(location="education", text=f"{ed.degree}, {ed.institution}",
                                 source_ids=[src.id] if src else [],
                                 status=_status([src.verification]) if ok else "unsupported"))
    for c in resume.certifications:
        src = next((x for x in profile.certifications if x.id == c.certification_id), None)
        ok = bool(src and src.name == c.name and (format_month(src.date) or src.date_text) == c.date)
        claims.append(ClaimTrace(location="certifications", text=c.name, source_ids=[src.id] if src else [],
                                 status=_status([src.verification]) if ok else "unsupported"))
    # Skills: each item must map to a profile skill (posting wording allowed only for the same skill).
    skill_by_id = {s.id: s for s in profile.skills}
    for line in resume.skills:
        for item in line.items:
            ids = line.sources.get(item, [])
            srcs = [skill_by_id[i] for i in ids if i in skill_by_id]
            ok = bool(srcs)
            if ok:
                canon_item = tax.canonical(item)
                ok = any(canon_item in (None, s.name) or s.name in tax.ancestors(canon_item or "")
                         or (canon_item and canon_item in tax.ancestors(s.name)) for s in srcs)
            claims.append(ClaimTrace(location="skills", text=item, source_ids=ids,
                                     status=_status([s.verification for s in srcs]) if ok else "unsupported",
                                     detail="" if ok else "No matching skill in the profile"))
    # Summary sentences
    for s in resume.summary:
        if s.kind == "result":
            found = profile.find_achievement(s.source_ids[0]) if s.source_ids else None
            if not found:
                claims.append(ClaimTrace(location="summary", text=s.text, source_ids=s.source_ids, status="unsupported"))
                continue
            ach, parent = found
            academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
            fc = fact_check(s.text, [ach.text, ach.original_text], academic=academic)
            if not fc.passed:
                problems.extend(f"Summary: {p}" for p in fc.problems)
            claims.append(ClaimTrace(location="summary", text=s.text, source_ids=s.source_ids,
                                     status=_status([ach.verification]) if fc.passed else "unsupported",
                                     detail="; ".join(fc.problems)))
        else:
            verifs = []
            for sid in s.source_ids:
                for group in (profile.roles, profile.projects, profile.education):
                    item = next((x for x in group if x.id == sid), None)
                    if item:
                        verifs.append(item.verification)
            claims.append(ClaimTrace(location="summary", text=s.text, source_ids=s.source_ids,
                                     status=_status(verifs) if s.source_ids else "supported_unverified",
                                     detail="Derived from profile facts (title, degree, employer, listed skills)"))
    total = len(claims) or 1
    unsupported = sum(1 for c in claims if c.status in ("unsupported", "rejected_source"))
    unverified = sum(1 for c in claims if c.status == "supported_unverified")
    verified = sum(1 for c in claims if c.status == "supported_verified")
    return IntegrityReport(score=round(100 * (total - unsupported) / total, 1), claims=claims, unsupported=unsupported,
                           unverified=unverified, verified=verified, fact_problems=problems,
                           employment_facts_preserved=employment_ok)


def _bullet_trace(profile: CandidateProfile, b, location: str, problems: list[str]) -> ClaimTrace:
    sources = [profile.find_achievement(i) for i in b.achievement_ids]
    if not b.achievement_ids or any(s is None for s in sources):
        return ClaimTrace(location=location, text=b.text, source_ids=b.achievement_ids, status="unsupported",
                          detail="No source achievement")
    achs = [s[0] for s in sources]
    parent = sources[0][1]
    academic = isinstance(parent, Project) and parent.context in ("academic", "personal")
    texts = [t for a in achs for t in (a.text, a.original_text)]
    fc = fact_check(b.text, texts, academic=academic)
    if not fc.passed and b.text.strip() not in [t.strip() for t in texts]:
        problems.extend(f"{b.text[:50]}...: {p}" for p in fc.problems)
        return ClaimTrace(location=location, text=b.text, source_ids=b.achievement_ids, status="unsupported",
                          detail="; ".join(fc.problems))
    detail = ""
    if not fc.passed:
        detail = "Original wording contains claims that need confirmation: " + "; ".join(fc.problems)
    if any(a.allowed_usage == "do_not_use" for a in achs):
        return ClaimTrace(location=location, text=b.text, source_ids=b.achievement_ids, status="rejected_source",
                          detail="Marked do-not-use in the profile")
    return ClaimTrace(location=location, text=b.text, source_ids=b.achievement_ids,
                      status=_status([a.verification for a in achs]), detail=detail)
