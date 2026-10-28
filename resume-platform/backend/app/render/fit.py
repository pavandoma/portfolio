"""Fit a resume to its page target without shrinking text into unreadability.

Order of operations: modest spacing/size steps first (10.5 -> 10 pt, 0.6 -> 0.55 in), then remove
the least relevant content, and only then a final small step (9.5 pt / 0.5 in). If it still does
not fit, the page target grows by one rather than going smaller.
"""

from __future__ import annotations

from app.render.pdf_writer import last_page_fill, page_count, render_pdf
from app.schemas.resume import OmittedItem, TailoredResume

MIN_FONT = 9.5
MIN_MARGIN = 0.5


def _drop_lowest_bullet(resume: TailoredResume) -> OmittedItem | None:
    candidates = []
    for e in resume.experience:
        if len(e.bullets) > 2:
            b = min(e.bullets, key=lambda b: b.relevance)
            candidates.append((b.relevance, "experience", e, b))
    for p in resume.projects:
        if len(p.bullets) > 1:
            b = min(p.bullets, key=lambda b: b.relevance)
            candidates.append((b.relevance * 0.9, "project", p, b))
    if not candidates:
        return None
    _rel, _kind, parent, bullet = min(candidates, key=lambda c: (c[0], c[3].id))
    parent.bullets.remove(bullet)
    return OmittedItem(item_type="bullet", item_id=bullet.achievement_ids[0], text=bullet.text,
                       reason="Removed to fit the page target (least relevant bullet)")


def _drop_lowest_project(resume: TailoredResume) -> OmittedItem | None:
    if len(resume.projects) <= 1:
        return None
    p = min(resume.projects, key=lambda p: max((b.relevance for b in p.bullets), default=0))
    resume.projects.remove(p)
    return OmittedItem(item_type="project", item_id=p.project_id, text=p.name,
                       reason="Removed to fit the page target (least relevant project)")


def _trim_skills(resume: TailoredResume, keep: int) -> OmittedItem | None:
    total = sum(len(line.items) for line in resume.skills)
    if total <= keep:
        return None
    longest = max(resume.skills, key=lambda line: len(line.items))
    item = longest.items.pop()
    if not longest.items:
        resume.skills.remove(longest)
    return OmittedItem(item_type="skill", item_id=item, text=item, reason="Removed to fit the page target")


def fit_resume(resume: TailoredResume, *, max_steps: int = 40, reserve_projects=None,
               reserve_bullets=None) -> tuple[TailoredResume, bytes, list[str]]:
    resume = resume.model_copy(deep=True)
    actions: list[str] = []
    target = resume.layout.page_target
    pdf = render_pdf(resume)
    steps = 0

    def fits() -> bool:
        return page_count(pdf) <= target

    if not fits() and resume.layout.body_font_size > 10.0:
        resume.layout.body_font_size, resume.layout.margin_in = 10.0, 0.55
        pdf = render_pdf(resume)
        actions.append("Body text 10 pt, margins 0.55 in")
    while not fits() and steps < max_steps:
        steps += 1
        dropped = _drop_lowest_bullet(resume)
        if dropped is None and len(resume.projects) > 2:
            dropped = _drop_lowest_project(resume)
        if dropped is None:
            dropped = _trim_skills(resume, keep=16)
        if dropped is None:
            break
        resume.omitted.append(dropped)
        actions.append(f"Removed {dropped.item_type}: {dropped.text[:60]}")
        pdf = render_pdf(resume)
    if not fits() and resume.layout.body_font_size > MIN_FONT:
        resume.layout.body_font_size, resume.layout.margin_in = MIN_FONT, MIN_MARGIN
        pdf = render_pdf(resume)
        actions.append(f"Body text {MIN_FONT} pt, margins {MIN_MARGIN} in (minimum)")
    if not fits():
        # A barely spilling second page is better than unreadable text.
        resume.layout.page_target = page_count(pdf)
        actions.append(f"Content needs {resume.layout.page_target} pages at a readable size; page target raised")
    elif page_count(pdf) > 1 and last_page_fill(pdf) < 0.15:
        actions.append("Last page is nearly empty; consider trimming one more bullet")
    if fits():
        pdf = _fill_space(resume, pdf, target, reserve_projects or [], reserve_bullets or [], actions)
    return resume, pdf, actions


def _fill_space(resume: TailoredResume, pdf: bytes, target: int, projects, bullets, actions) -> bytes:
    """Use leftover space for content that was cut only for space, most relevant first."""
    pool = [("bullet", b.relevance, (role_id, b)) for role_id, b in bullets] + \
        [("project", max((b.relevance for b in p.bullets), default=0), p) for p in projects]
    pool.sort(key=lambda t: -t[1])
    for kind, _rel, item in pool:
        if page_count(pdf) == target and last_page_fill(pdf) > 0.86:
            break
        trial = resume.model_copy(deep=True)
        if kind == "bullet":
            role_id, bullet = item
            entry = next((e for e in trial.experience if e.role_id == role_id), None)
            if entry is None:
                continue
            entry.bullets.append(bullet)
            restored_id = bullet.achievement_ids[0]
        else:
            trial.projects.append(item)
            restored_id = item.project_id
        trial_pdf = render_pdf(trial)
        if page_count(trial_pdf) <= target:
            trial.omitted = [o for o in trial.omitted if o.item_id != restored_id]
            resume.__dict__.update(trial.__dict__)
            pdf = trial_pdf
            actions.append(f"Restored {kind} to use free space: "
                           f"{(item[1].text if kind == 'bullet' else item.name)[:60]}")
    return pdf
