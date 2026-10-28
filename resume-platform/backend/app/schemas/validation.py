"""Validation reports: ATS parsing, evidence integrity, content QA, external validators."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import Severity

CheckStatus = Literal["pass", "warn", "fail", "skipped"]


class FieldCheck(BaseModel):
    field: str
    expected: str
    extracted: str | None = None
    status: CheckStatus
    detail: str = ""


class FormatCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str = ""


class ATSReport(BaseModel):
    extractor: str
    document_kind: Literal["pdf", "docx"]
    score: float  # 0..100
    page_count: int = 0
    fields: list[FieldCheck] = Field(default_factory=list)
    checks: list[FormatCheck] = Field(default_factory=list)
    extracted_text_sample: str = ""

    @property
    def critical_failures(self) -> list[FieldCheck]:
        return [f for f in self.fields if f.status == "fail"]


class ClaimTrace(BaseModel):
    location: str
    text: str
    source_ids: list[str]
    status: Literal["supported_verified", "supported_unverified", "unsupported", "rejected_source"]
    detail: str = ""


class IntegrityReport(BaseModel):
    score: float  # 0..100, share of claims traced to non-rejected evidence
    claims: list[ClaimTrace] = Field(default_factory=list)
    unsupported: int = 0
    unverified: int = 0
    verified: int = 0
    fact_problems: list[str] = Field(default_factory=list)
    employment_facts_preserved: bool = True


class QAIssue(BaseModel):
    category: Literal["content", "formatting", "style"]
    code: str
    severity: Severity
    location: str
    message: str
    suggestion: str = ""


class QAReport(BaseModel):
    score: float
    issues: list[QAIssue] = Field(default_factory=list)


class ExternalValidatorResult(BaseModel):
    adapter: str
    category: Literal["matcher", "parser", "internal"]
    status: Literal["ok", "unavailable", "error", "not_authorized", "skipped"]
    detail: str = ""
    score: float | None = None  # only ever set from a real response
    raw: dict[str, Any] | None = None


class ValidationBundle(BaseModel):
    ats: list[ATSReport] = Field(default_factory=list)
    integrity: IntegrityReport
    qa: QAReport
    external: list[ExternalValidatorResult] = Field(default_factory=list)
