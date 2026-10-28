"""Adapters that run locally: the internal PyMuPDF / python-docx parse-back and poppler's pdftotext."""

from __future__ import annotations

from app.schemas.validation import ExternalValidatorResult
from app.validation import ats
from app.validation.adapters.base import ValidationContext


class InternalPdfParser:
    name = "internal-pymupdf"
    category = "internal"
    sends_data_externally = False

    def availability(self) -> tuple[bool, str]:
        return True, "Built in"

    def run(self, ctx: ValidationContext) -> ExternalValidatorResult:
        if not ctx.pdf:
            return ExternalValidatorResult(adapter=self.name, category="internal", status="skipped", detail="No PDF")
        rep = ats.check_pdf(ctx.pdf, ctx.resume)
        failed = [f.field for f in rep.fields if f.status == "fail"]
        return ExternalValidatorResult(adapter=self.name, category="internal", status="ok", score=rep.score,
                                       detail="All fields extracted" if not failed else "Failed: " + ", ".join(failed),
                                       raw={"fields": [f.model_dump() for f in rep.fields]})


class PopplerParser:
    """Independent extraction engine (poppler-utils). Local process; no data leaves the machine."""

    name = "poppler-pdftotext"
    category = "parser"
    sends_data_externally = False

    def availability(self) -> tuple[bool, str]:
        ok = ats.pdftotext_available()
        return ok, "pdftotext found on PATH" if ok else "Install poppler-utils to enable"

    def run(self, ctx: ValidationContext) -> ExternalValidatorResult:
        ok, why = self.availability()
        if not ok:
            return ExternalValidatorResult(adapter=self.name, category="parser", status="unavailable", detail=why)
        if not ctx.pdf:
            return ExternalValidatorResult(adapter=self.name, category="parser", status="skipped", detail="No PDF")
        rep = ats.check_pdf_with_pdftotext(ctx.pdf, ctx.resume)
        if rep is None:
            return ExternalValidatorResult(adapter=self.name, category="parser", status="error", detail="pdftotext failed")
        failed = [f.field for f in rep.fields if f.status == "fail"]
        return ExternalValidatorResult(adapter=self.name, category="parser", status="ok", score=rep.score,
                                       detail="All fields extracted" if not failed else "Failed: " + ", ".join(failed),
                                       raw={"fields": [f.model_dump() for f in rep.fields]})
