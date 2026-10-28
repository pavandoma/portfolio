"""Shared vocabulary used across the profile, job, matching and resume models."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

VerificationStatus = Literal["unverified", "verified", "needs_review", "rejected", "user_corrected"]
EvidenceStrength = Literal["strong", "moderate", "weak", "none"]
# any: the tailoring engine may reword it; with_care: keep wording close to the source;
# do_not_use: never place it on a resume.
AllowedUsage = Literal["any", "with_care", "do_not_use"]
Severity = Literal["info", "warning", "critical"]
FlagKind = Literal[
    "metric",
    "absolute_claim",
    "collaboration",
    "production",
    "leadership",
    "deployment",
    "causal_clarity",
    "academic_vs_production",
    "grammar",
    "unsupported_skill",
    "conflict",
    "title",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stable_id(prefix: str, *parts: str, length: int = 10) -> str:
    """Deterministic identifier so re-importing the same source yields the same ids."""
    digest = hashlib.sha1("␟".join(parts).encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


class SourceRef(BaseModel):
    """Where a fact came from. ``original_text`` is the verbatim source wording."""

    document_id: str | None = None
    document_name: str | None = None
    page: int | None = None
    section: str | None = None
    line: int | None = None
    original_text: str = ""


class Metric(BaseModel):
    raw: str
    value: float | None = None
    unit: str = ""
    context: str = ""


class ClaimFlag(BaseModel):
    kind: FlagKind
    span: str = ""
    message: str
    severity: Severity = "warning"


class FactCheck(BaseModel):
    """Result of comparing a rewritten sentence against its source evidence."""

    passed: bool
    problems: list[str] = Field(default_factory=list)
    new_numbers: list[str] = Field(default_factory=list)
    new_technologies: list[str] = Field(default_factory=list)
    new_risky_terms: list[str] = Field(default_factory=list)
