"""Validator adapter interface.

Three categories:
  * matcher  - external candidate/job matchers (score fit from their own model)
  * parser   - resume parsing validators (do the fields survive extraction?)
  * internal - this application's own evidence and parsing checks

Adapters are independent: any of them can be missing or failing without affecting the others.
A missing external result is reported as such; scores are only ever copied from a real response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.job import JobAnalysis
from app.schemas.resume import TailoredResume
from app.schemas.validation import ExternalValidatorResult


@dataclass
class ValidationContext:
    resume: TailoredResume
    resume_text: str
    pdf: bytes | None
    docx: bytes | None
    job: JobAnalysis | None
    job_text: str


class ValidatorAdapter(Protocol):
    name: str
    category: str
    sends_data_externally: bool

    def availability(self) -> tuple[bool, str]: ...

    def run(self, ctx: ValidationContext) -> ExternalValidatorResult: ...
