"""Structured job description analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RequirementCategory = Literal["mandatory", "preferred", "responsibility", "context"]
# explicit: a cue word in the line itself ("required", "nice to have", "must");
# section: inherited from the section heading; inferred: neither, the parser guessed.
CategoryBasis = Literal["explicit", "section", "inferred", "llm"]
RequirementKind = Literal[
    "skill",
    "experience_years",
    "education",
    "certification",
    "work_authorization",
    "clearance",
    "license",
    "responsibility",
    "soft_skill",
    "domain",
    "other",
]
WorkArrangement = Literal["remote", "hybrid", "onsite", "unknown"]
Seniority = Literal["intern", "entry", "mid", "senior", "staff", "principal", "lead", "manager", "unknown"]


class SkillMention(BaseModel):
    canonical: str
    as_written: str
    category: str | None = None


class Requirement(BaseModel):
    id: str
    text: str  # original wording from the posting
    category: RequirementCategory
    category_basis: CategoryBasis
    kind: RequirementKind
    skills: list[SkillMention] = Field(default_factory=list)
    # True when the line lists alternatives ("Python or Java", "such as ...").
    any_of: bool = False
    years: float | None = None
    years_subject: str | None = None
    degree_level: str | None = None
    degree_fields: list[str] = Field(default_factory=list)
    section: str | None = None
    line_no: int = 0
    importance: float = 0.0


class RankedSkill(BaseModel):
    canonical: str
    as_written: str  # the posting's own wording, used verbatim on the resume when justified
    category: str | None = None
    importance: float
    mentions: int
    in_mandatory: bool = False
    in_preferred: bool = False
    in_title: bool = False


class AuthorizationRequirement(BaseModel):
    text: str
    restriction: Literal["no_sponsorship", "citizenship", "clearance", "authorized_to_work", "license", "other"]


class JobAnalysis(BaseModel):
    title: str = ""
    title_basis: Literal["labelled", "first_line", "pattern", "user", "unknown"] = "unknown"
    company: str | None = None
    location: str | None = None
    work_arrangement: WorkArrangement = "unknown"
    seniority: Seniority = "unknown"
    employment_type: str | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    skill_importance: list[RankedSkill] = Field(default_factory=list)
    authorization: list[AuthorizationRequirement] = Field(default_factory=list)
    min_years_experience: float | None = None
    education_requirements: list[str] = Field(default_factory=list)  # requirement ids
    certification_requirements: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    injection_warnings: list[str] = Field(default_factory=list)
    extraction_method: str = "deterministic"
    parser_version: str = ""

    def by_category(self, category: RequirementCategory) -> list[Requirement]:
        return [r for r in self.requirements if r.category == category]

    def skills_in(self, category_group: str) -> list[RankedSkill]:
        return [s for s in self.skill_importance if s.category == category_group]
