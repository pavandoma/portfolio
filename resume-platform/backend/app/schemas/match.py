"""Matching and scoring results.

Four separate measurements are produced and never merged into a single "ATS score":

* Job Fit: how well the candidate's (master profile) qualifications match the role.
* Resume Alignment: how well a specific resume communicates those qualifications.
* ATS Parsing: whether important fields survive text extraction of the rendered file.
* Evidence Integrity: whether every resume claim traces back to candidate sources.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EvidenceLevel = Literal["direct", "partial", "related", "none", "unknown"]
GateStatus = Literal["met", "not_met", "unclear", "needs_user_input"]

EVIDENCE_LEVEL_LABELS: dict[str, str] = {
    "direct": "Directly demonstrated",
    "partial": "Partially demonstrated",
    "related": "Related but insufficient",
    "none": "Not demonstrated",
    "unknown": "Unknown",
}


class EvidenceLink(BaseModel):
    target_type: Literal["achievement", "skill", "role", "project", "education", "certification", "profile"]
    target_id: str
    excerpt: str = ""
    reason: str = ""
    verification: str | None = None


class RequirementMatch(BaseModel):
    requirement_id: str
    requirement_text: str
    category: str
    kind: str
    importance: float
    level: EvidenceLevel
    level_label: str
    score: float  # 0..1 credit used by the scorer
    explanation: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class GateResult(BaseModel):
    gate: str
    requirement_id: str | None = None
    requirement_text: str = ""
    status: GateStatus
    explanation: str


class DimensionScore(BaseModel):
    key: str
    label: str
    weight: float
    score: float  # 0..1
    points: float  # weight * score
    explanation: str
    details: list[str] = Field(default_factory=list)


class ScoreCard(BaseModel):
    name: str
    total: float  # 0..100
    dimensions: list[DimensionScore]
    notes: list[str] = Field(default_factory=list)


class Weights(BaseModel):
    required: float = 30
    experience: float = 25
    keywords: float = 15
    impact: float = 15
    ats: float = 10
    clarity: float = 5

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()


class MatchReport(BaseModel):
    job_title: str
    company: str | None = None
    job_fit: ScoreCard
    requirement_matches: list[RequirementMatch]
    gates: list[GateResult]
    strengths: list[str] = Field(default_factory=list)
    missing_mandatory: list[str] = Field(default_factory=list)
    missing_preferred: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    weights: Weights
    scoring_version: str
    input_hash: str
    disclaimer: str = (
        "These are transparent heuristics computed by this tool. They are not an employer's ATS "
        "score and do not predict the probability of an interview."
    )
