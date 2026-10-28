"""A tailored resume document, plus its change log.

Every line that makes a factual statement carries the ids of the profile records that
support it, so the evidence-integrity validator can trace each claim back to its source.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import ClaimFlag

LineOrigin = Literal["original", "rule_cleanup", "assistant", "llm", "user"]


class ResumeBullet(BaseModel):
    id: str
    text: str
    achievement_ids: list[str]
    variant_id: str | None = None
    origin: LineOrigin = "original"
    approved: bool = True
    relevance: float = 0.0
    matched_requirements: list[str] = Field(default_factory=list)
    flags: list[ClaimFlag] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    role_id: str
    title: str  # historical title, never changed to match a posting
    organization: str
    location: str | None = None
    date_range: str
    bullets: list[ResumeBullet] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    project_id: str
    name: str
    descriptor: str | None = None  # e.g. "Academic project"
    technologies: list[str] = Field(default_factory=list)
    date_range: str = ""
    bullets: list[ResumeBullet] = Field(default_factory=list)


class EducationLine(BaseModel):
    education_id: str
    degree: str
    institution: str
    location: str | None = None
    date: str = ""
    gpa: str | None = None


class CertificationLine(BaseModel):
    certification_id: str
    name: str
    detail: str | None = None
    date: str = ""


class SkillLine(BaseModel):
    category: str
    items: list[str]
    # canonical skill -> skill ids in the profile, for traceability
    sources: dict[str, list[str]] = Field(default_factory=dict)


class SummarySentence(BaseModel):
    text: str
    kind: Literal["identity", "skills", "result", "value"]
    source_ids: list[str] = Field(default_factory=list)


class ResumeHeader(BaseModel):
    name: str
    target_title: str
    contact: list[str]
    links: list[str] = Field(default_factory=list)


class LayoutSettings(BaseModel):
    page_target: int = 1
    body_font_size: float = 10.5
    margin_in: float = 0.6
    font_family: Literal["sans", "serif"] = "sans"


class OmittedItem(BaseModel):
    item_type: Literal["bullet", "project", "skill", "role", "certification"]
    item_id: str
    text: str
    reason: str


class TailoredResume(BaseModel):
    header: ResumeHeader
    summary: list[SummarySentence] = Field(default_factory=list)
    skills: list[SkillLine] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    education: list[EducationLine] = Field(default_factory=list)
    certifications: list[CertificationLine] = Field(default_factory=list)
    section_order: list[str] = Field(
        default_factory=lambda: ["summary", "skills", "experience", "projects", "education", "certifications"]
    )
    layout: LayoutSettings = Field(default_factory=LayoutSettings)
    omitted: list[OmittedItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    top_requirements: list[str] = Field(default_factory=list)
    variant: str | None = None

    @property
    def summary_text(self) -> str:
        return " ".join(s.text for s in self.summary)

    def all_bullets(self) -> list[ResumeBullet]:
        out: list[ResumeBullet] = []
        for e in self.experience:
            out.extend(e.bullets)
        for p in self.projects:
            out.extend(p.bullets)
        return out


class ChangeLogEntry(BaseModel):
    kind: Literal[
        "title", "summary", "skills_reordered", "skill_removed", "skill_added", "bullet_reworded",
        "bullet_removed", "bullet_reordered", "project_removed", "section_reordered", "revision",
    ]
    target: str
    before: str | None = None
    after: str | None = None
    reason: str
    evidence_ids: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class DiffToken(BaseModel):
    op: Literal["equal", "insert", "delete"]
    text: str


class BulletDiff(BaseModel):
    target: str
    achievement_ids: list[str]
    before: str
    after: str
    tokens: list[DiffToken]
    origin: str
    approved: bool
    position_before: int | None = None
    position_after: int | None = None
