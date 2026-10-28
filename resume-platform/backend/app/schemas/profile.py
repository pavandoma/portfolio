"""Master candidate profile.

The profile is stored as immutable revisions: every correction or approval creates a new
revision and an audit event, and tailored resumes pin the revision they were built from.
Verification status is stored next to (not inside) the extracted wording, so the original
source text is never lost.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import (
    AllowedUsage,
    ClaimFlag,
    EvidenceStrength,
    FactCheck,
    Metric,
    Severity,
    SourceRef,
    VerificationStatus,
    utcnow,
)

VariantOrigin = Literal["original", "rule_cleanup", "assistant", "llm", "user"]


class Link(BaseModel):
    label: str
    url: str


class PersonalInfo(BaseModel):
    name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[Link] = Field(default_factory=list)
    source_ref: SourceRef | None = None
    verification: VerificationStatus = "unverified"


class PhrasingVariant(BaseModel):
    """Alternative wording for one achievement. Wording is presentation, never evidence."""

    id: str
    text: str
    emphasis: list[str] = Field(default_factory=list)
    origin: VariantOrigin
    approved: bool = False
    fact_check: FactCheck | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Achievement(BaseModel):
    id: str
    text: str
    original_text: str
    source_ref: SourceRef
    verification: VerificationStatus = "unverified"
    technologies: list[str] = Field(default_factory=list)
    competencies: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    flags: list[ClaimFlag] = Field(default_factory=list)
    evidence_strength: EvidenceStrength = "weak"
    allowed_usage: AllowedUsage = "any"
    evidence_ids: list[str] = Field(default_factory=list)
    variants: list[PhrasingVariant] = Field(default_factory=list)
    note: str | None = None
    last_modified: datetime = Field(default_factory=utcnow)


EmploymentType = Literal[
    "full_time", "part_time", "internship", "student_employment", "contract", "unknown"
]


class Role(BaseModel):
    id: str
    title: str
    organization: str
    location: str | None = None
    start: str | None = None  # YYYY-MM
    end: str | None = None  # YYYY-MM or "present"
    date_text: str = ""  # dates exactly as written in the source
    employment_type: EmploymentType = "unknown"
    source_ref: SourceRef
    verification: VerificationStatus = "unverified"
    achievements: list[Achievement] = Field(default_factory=list)


ProjectContext = Literal["academic", "personal", "professional", "open_source", "unknown"]


class Project(BaseModel):
    id: str
    name: str
    subtitle: str | None = None
    context: ProjectContext = "unknown"
    url: str | None = None
    repo_url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    date_text: str = ""
    source_ref: SourceRef
    verification: VerificationStatus = "unverified"
    achievements: list[Achievement] = Field(default_factory=list)


class Education(BaseModel):
    id: str
    institution: str
    degree: str
    field: str | None = None
    level: Literal["associate", "bachelor", "master", "doctorate", "certificate", "other"] = "other"
    location: str | None = None
    end: str | None = None  # YYYY-MM
    date_text: str = ""
    status: Literal["completed", "expected", "unknown"] = "unknown"
    gpa: str | None = None
    source_ref: SourceRef
    verification: VerificationStatus = "unverified"


class Certification(BaseModel):
    id: str
    name: str
    detail: str | None = None
    issuer: str | None = None
    date: str | None = None  # YYYY-MM
    date_text: str = ""
    credential_url: str | None = None
    source_ref: SourceRef
    verification: VerificationStatus = "unverified"


class Skill(BaseModel):
    id: str
    name: str  # canonical name from the taxonomy (or the written form if unknown)
    display: str  # exactly as written in the source
    category: str | None = None  # the source's own grouping label
    taxonomy_category: str | None = None
    source_ref: SourceRef | None = None
    verification: VerificationStatus = "unverified"
    # Derived: achievements that actually demonstrate this skill.
    evidence_achievement_ids: list[str] = Field(default_factory=list)
    # True when the skill only appears in a skills list, with no supporting bullet.
    self_reported_only: bool = True
    # True when the skill was found in a bullet but was not listed in the skills section.
    derived_from_bullets: bool = False


EvidenceKind = Literal["document", "repository", "link", "note", "certificate"]


class Evidence(BaseModel):
    id: str
    kind: EvidenceKind
    title: str
    uri: str | None = None
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    linked_ids: list[str] = Field(default_factory=list)
    source_document_id: str | None = None
    added_at: datetime = Field(default_factory=utcnow)


IssueKind = Literal[
    "unsupported_claim", "conflict", "missing_field", "needs_verification", "formatting", "injection"
]


class ProfileIssue(BaseModel):
    id: str
    kind: IssueKind
    target_id: str | None = None
    field: str | None = None
    message: str
    severity: Severity = "warning"
    status: Literal["open", "resolved", "dismissed"] = "open"
    options: list[str] = Field(default_factory=list)
    resolution: str | None = None


WorkAuthStatus = Literal[
    "unknown",
    "citizen",
    "permanent_resident",
    "authorized_no_sponsorship",
    "authorized_requires_future_sponsorship",
    "requires_sponsorship",
]


class WorkAuthorization(BaseModel):
    status: WorkAuthStatus = "unknown"
    note: str | None = None
    has_security_clearance: bool | None = None
    licenses: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    schema_version: int = 1
    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    original_summary: str | None = None
    roles: list[Role] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    issues: list[ProfileIssue] = Field(default_factory=list)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    source_document_ids: list[str] = Field(default_factory=list)

    # -- helpers -------------------------------------------------------------
    def all_achievements(self) -> list[tuple[Achievement, Role | Project]]:
        out: list[tuple[Achievement, Role | Project]] = []
        for r in self.roles:
            out.extend((a, r) for a in r.achievements)
        for p in self.projects:
            out.extend((a, p) for a in p.achievements)
        return out

    def find_achievement(self, achievement_id: str) -> tuple[Achievement, Role | Project] | None:
        for a, parent in self.all_achievements():
            if a.id == achievement_id:
                return a, parent
        return None

    def usable_achievements(self) -> list[tuple[Achievement, Role | Project]]:
        return [
            (a, p)
            for a, p in self.all_achievements()
            if a.verification != "rejected" and a.allowed_usage != "do_not_use"
        ]

    def skill_names(self) -> set[str]:
        return {s.name for s in self.skills if s.verification != "rejected"}
