"""Before/after comparison between the master profile wording and a tailored resume."""

from __future__ import annotations

import difflib
import re

from app.schemas.profile import CandidateProfile
from app.schemas.resume import BulletDiff, DiffToken, TailoredResume


def token_diff(before: str, after: str) -> list[DiffToken]:
    a = re.findall(r"\S+|\s+", before)
    b = re.findall(r"\S+|\s+", after)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    out: list[DiffToken] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(DiffToken(op="equal", text="".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(DiffToken(op="delete", text="".join(a[i1:i2])))
            if j2 > j1:
                out.append(DiffToken(op="insert", text="".join(b[j1:j2])))
    return out


def bullet_diffs(profile: CandidateProfile, resume: TailoredResume) -> list[BulletDiff]:
    diffs: list[BulletDiff] = []
    entries = [(e.role_id, e.bullets) for e in resume.experience] + [(p.project_id, p.bullets) for p in resume.projects]
    for parent_id, bullets in entries:
        parent = next((x for x in [*profile.roles, *profile.projects] if x.id == parent_id), None)
        for pos, b in enumerate(bullets):
            found = profile.find_achievement(b.achievement_ids[0])
            if not found:
                continue
            ach, _ = found
            before = ach.original_text
            orig_pos = parent.achievements.index(ach) if parent else None
            diffs.append(BulletDiff(target=b.id, achievement_ids=b.achievement_ids, before=before, after=b.text,
                                    tokens=token_diff(before, b.text), origin=b.origin, approved=b.approved,
                                    position_before=orig_pos, position_after=pos))
    return diffs


def resume_plain_text(resume: TailoredResume) -> str:
    """Plain-text rendering, used for keyword checks and the side-by-side view."""
    lines = [resume.header.name, resume.header.target_title, " | ".join(resume.header.contact), ""]
    for sec in resume.section_order:
        if sec == "summary" and resume.summary:
            lines += [" ".join(s.text for s in resume.summary), ""]
        elif sec == "skills" and resume.skills:
            lines += ["SKILLS"] + [f"{s.category}: {', '.join(s.items)}" for s in resume.skills] + [""]
        elif sec == "experience" and resume.experience:
            lines.append("PROFESSIONAL EXPERIENCE")
            for e in resume.experience:
                lines += [f"{e.title} | {e.organization} | {e.location or ''} | {e.date_range}"]
                lines += [f"- {b.text}" for b in e.bullets]
            lines.append("")
        elif sec == "projects" and resume.projects:
            lines.append("PROJECTS")
            for p in resume.projects:
                lines += [f"{p.name}" + (f" ({p.descriptor})" if p.descriptor else "")]
                lines += [f"- {b.text}" for b in p.bullets]
            lines.append("")
        elif sec == "education" and resume.education:
            lines += ["EDUCATION"] + [f"{e.degree}, {e.institution} | {e.date}" for e in resume.education] + [""]
        elif sec == "certifications" and resume.certifications:
            lines += ["CERTIFICATIONS"] + [f"{c.name} | {c.date}" for c in resume.certifications]
    return "\n".join(lines).strip()


def original_plain_text(profile: CandidateProfile) -> str:
    p = profile.personal
    lines = [p.name, " | ".join(x for x in (p.email, p.phone, *(lk.url for lk in p.links)) if x), ""]
    if profile.original_summary:
        lines += [profile.original_summary, ""]
    if profile.skills:
        cats: dict[str, list[str]] = {}
        for s in profile.skills:
            if not s.derived_from_bullets:
                cats.setdefault(s.category or "Skills", []).append(s.display)
        lines += ["SKILLS"] + [f"{k}: {', '.join(v)}" for k, v in cats.items()] + [""]
    lines.append("EXPERIENCE")
    for r in profile.roles:
        lines.append(f"{r.title} | {r.organization} | {r.location or ''} | {r.date_text}")
        lines += [f"- {a.original_text}" for a in r.achievements]
    lines += ["", "PROJECTS"]
    for pr in profile.projects:
        lines.append(pr.name + (f" ({pr.subtitle})" if pr.subtitle else ""))
        lines += [f"- {a.original_text}" for a in pr.achievements]
    lines += ["", "EDUCATION"] + [f"{e.degree}, {e.institution} | {e.date_text}" for e in profile.education]
    lines += ["", "CERTIFICATIONS"] + [f"{c.name} | {c.date_text}" for c in profile.certifications]
    return "\n".join(lines).strip()
