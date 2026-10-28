"""ATS parsing check: does the important information survive text extraction?

The generated file is extracted again from scratch (PyMuPDF for PDF, python-docx for DOCX,
and optionally poppler's pdftotext as a second, independent engine), parsed with the generic
resume parser, and compared field by field with what the resume was supposed to say.

This is a parsing-robustness measure computed by this tool. It is not an employer's ATS score.
"""

from __future__ import annotations

import re
import shutil
import subprocess

from app.core.dates import find_date_range
from app.core.text import clean_text
from app.ingest.extract import ExtractedDocument, extract_docx, extract_pdf, extract_text
from app.ingest.resume_parser import ParsedResume, parse_resume
from app.schemas.resume import TailoredResume
from app.schemas.validation import ATSReport, FieldCheck, FormatCheck

FIELD_WEIGHTS = {"name": 3, "email": 3, "phone": 2, "link": 1, "title": 2, "headings": 3, "role": 3,
                 "education": 2, "project": 1, "certification": 1, "skills": 2, "summary": 1, "bullets": 2}
SECTION_LABELS = {"skills": "skills", "experience": "experience", "projects": "projects", "education": "education",
                  "certifications": "certifications"}


def _digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _status(ok: bool, partial: bool = False) -> str:
    return "pass" if ok else ("warn" if partial else "fail")


def compare_fields(parsed: ParsedResume, doc: ExtractedDocument, resume: TailoredResume) -> list[FieldCheck]:
    checks: list[FieldCheck] = []
    text = doc.text
    norm_text = _norm(text)
    h = resume.header
    checks.append(FieldCheck(field="name", expected=h.name, extracted=parsed.name,
                             status=_status(_norm(parsed.name) == _norm(h.name)),
                             detail="Name must be the first, largest line."))
    checks.append(FieldCheck(field="target_title", expected=h.target_title, extracted=parsed.headline,
                             status=_status(_norm(parsed.headline) == _norm(h.target_title),
                                            _norm(h.target_title) in norm_text)))
    for item in h.contact:
        if "@" in item:
            ok = item.lower() in [e.lower() for e in parsed.emails]
            checks.append(FieldCheck(field="email", expected=item, extracted=", ".join(parsed.emails), status=_status(ok)))
        elif len(_digits(item)) >= 10:
            ok = any(_digits(p).endswith(_digits(item)[-10:]) for p in parsed.phones)
            checks.append(FieldCheck(field="phone", expected=item, extracted=", ".join(parsed.phones), status=_status(ok)))
        elif "." in item and "/" in item:
            ok = any(_norm(item) in _norm(u) for u in parsed.urls) or _norm(item) in norm_text
            checks.append(FieldCheck(field="link", expected=item, extracted=", ".join(parsed.urls), status=_status(ok)))
    expected_sections = [s for s in resume.section_order if s in SECTION_LABELS and _has_content(resume, s)]
    found = [s for s in parsed.section_order if s in SECTION_LABELS]
    missing = [s for s in expected_sections if s not in found]
    in_order = [s for s in found if s in expected_sections] == expected_sections
    checks.append(FieldCheck(field="section_headings", expected=", ".join(expected_sections), extracted=", ".join(found),
                             status=_status(not missing and in_order, not missing),
                             detail="" if not missing else f"Not detected: {', '.join(missing)}"))
    if resume.summary:
        ok = parsed.summary is not None and _norm(resume.summary[0].text)[:40] in _norm(parsed.summary)
        checks.append(FieldCheck(field="summary", expected=resume.summary[0].text[:80], extracted=(parsed.summary or "")[:80],
                                 status=_status(ok, _norm(resume.summary[0].text)[:40] in norm_text)))
    for i, e in enumerate(resume.experience):
        got = parsed.experience[i] if i < len(parsed.experience) else None
        exp_dr = find_date_range(e.date_range)
        title_ok = bool(got and _norm(got.title) == _norm(e.title))
        org_ok = bool(got and _norm(got.organization) == _norm(e.organization))
        date_ok = bool(got and exp_dr and (got.start, got.end) == (exp_dr[0], exp_dr[1]))
        loc_ok = bool(got and (not e.location or _norm(got.location) == _norm(e.location)))
        checks.append(FieldCheck(field=f"experience[{i}].title", expected=e.title, extracted=got.title if got else None,
                                 status=_status(title_ok)))
        checks.append(FieldCheck(field=f"experience[{i}].employer", expected=e.organization,
                                 extracted=got.organization if got else None, status=_status(org_ok)))
        checks.append(FieldCheck(field=f"experience[{i}].dates", expected=e.date_range,
                                 extracted=got.date_text if got else None, status=_status(date_ok)))
        if e.location:
            checks.append(FieldCheck(field=f"experience[{i}].location", expected=e.location,
                                     extracted=got.location if got else None, status=_status(loc_ok, True)))
        n_ok = bool(got and len(got.bullets) == len(e.bullets))
        checks.append(FieldCheck(field=f"experience[{i}].bullets", expected=str(len(e.bullets)),
                                 extracted=str(len(got.bullets)) if got else "0", status=_status(n_ok, bool(got))))
    for i, ed in enumerate(resume.education):
        got = parsed.education[i] if i < len(parsed.education) else None
        ok = bool(got and _norm(got.organization) == _norm(ed.institution) and _norm(got.title) == _norm(ed.degree))
        checks.append(FieldCheck(field=f"education[{i}]", expected=f"{ed.degree} | {ed.institution} | {ed.date}",
                                 extracted=f"{got.title} | {got.organization} | {got.date_text}" if got else None,
                                 status=_status(ok, bool(got))))
    for i, p in enumerate(resume.projects):
        got = parsed.projects[i] if i < len(parsed.projects) else None
        ok = bool(got and _norm(p.name) in _norm(got.title + " " + " ".join(got.header)))
        checks.append(FieldCheck(field=f"projects[{i}]", expected=p.name, extracted=got.title if got else None,
                                 status=_status(ok, _norm(p.name) in norm_text)))
    for i, c in enumerate(resume.certifications):
        ok = _norm(c.name) in norm_text
        checks.append(FieldCheck(field=f"certifications[{i}]", expected=c.name, extracted=c.name if ok else None,
                                 status=_status(ok)))
    items = [i for line in resume.skills for i in line.items]
    if items:
        found_items = [i for i in items if _norm(i) in norm_text]
        ratio = len(found_items) / len(items)
        checks.append(FieldCheck(field="skills", expected=f"{len(items)} skills",
                                 extracted=f"{len(found_items)} found", status=_status(ratio == 1.0, ratio >= 0.8),
                                 detail="" if ratio == 1 else "Missing: " + ", ".join(i for i in items if i not in found_items)))
    return checks


def _has_content(resume: TailoredResume, section: str) -> bool:
    return bool(getattr(resume, section, None))


def format_checks(doc: ExtractedDocument, resume: TailoredResume, kind: str) -> list[FormatCheck]:
    checks: list[FormatCheck] = []
    text = doc.text
    checks.append(FormatCheck(name="selectable_text", status=_status(len(text) > 300),
                              detail=f"{len(text)} characters extracted"))
    broken = len(re.findall(r"�|\(cid:\d+\)|[-]", text))
    checks.append(FormatCheck(name="broken_characters", status=_status(broken == 0), detail=f"{broken} found"))
    checks.append(FormatCheck(name="no_images", status=_status(doc.image_count == 0),
                              detail=f"{doc.image_count} images" if doc.image_count else "Text only"))
    if kind == "pdf":
        expected_pages = resume.layout.page_target
        checks.append(FormatCheck(name="page_count", status=_status(doc.page_count <= expected_pages),
                                  detail=f"{doc.page_count} page(s), target {expected_pages}"))
        families = {re.sub(r"[-,](Bold|Italic|Regular|Oblique|BoldItalic|BoldOblique|Roman).*$", "", f) for f in doc.fonts}
        checks.append(FormatCheck(name="font_consistency", status=_status(len(families) <= 2, len(families) <= 3),
                                  detail=", ".join(sorted(families))))
        margin_text = [ln.text for ln in doc.lines if ln.region != "body"]
        checks.append(FormatCheck(name="no_header_footer_text", status=_status(not margin_text, True),
                                  detail="; ".join(margin_text)[:120] or "None"))
        centered = {resume.header.name.upper(), resume.header.target_title}
        right_col = [ln for ln in doc.lines if ln.x0 > doc.page_width * 0.45 and ln.text not in centered
                     and not any(c.isdigit() for c in ln.text[:4]) and len(ln.text) > 25]
        checks.append(FormatCheck(name="single_column", status=_status(len(right_col) <= 1, len(right_col) <= 3),
                                  detail=f"{len(right_col)} lines start in the right half"))
        if doc.lines and doc.page_count == 1:
            last_y = max(ln.y for ln in doc.lines)
            fill = last_y / doc.page_height
            checks.append(FormatCheck(name="whitespace", status=_status(fill >= 0.7, fill >= 0.55),
                                      detail=f"Content uses {fill:.0%} of the page height"))
    else:
        checks.append(FormatCheck(name="no_header_footer_text", status=_status(not doc.header_footer_text),
                                  detail="; ".join(doc.header_footer_text)[:120] or "None"))
        checks.append(FormatCheck(name="no_tables", status=_status(not doc.warnings), detail="; ".join(doc.warnings) or "None"))
    headings = [ln.text for ln in doc.lines if ln.bold and ln.text.isupper() and len(ln.text.split()) <= 3
                and ln.text != resume.header.name.upper()]
    checks.append(FormatCheck(name="heading_consistency", status=_status(all(h.isupper() for h in headings)),
                              detail=", ".join(headings)))
    return checks


def _score(fields: list[FieldCheck], fmt: list[FormatCheck]) -> float:
    def w(f: FieldCheck) -> int:
        base = f.field.split("[")[0].split(".")[0]
        key = {"target_title": "title", "section_headings": "headings", "experience": "role", "projects": "project",
               "certifications": "certification"}.get(base, base)
        if ".bullets" in f.field:
            key = "bullets"
        return FIELD_WEIGHTS.get(key, 1)

    total = sum(w(f) for f in fields) or 1
    got = sum(w(f) * {"pass": 1.0, "warn": 0.5}.get(f.status, 0.0) for f in fields)
    if not fmt:
        return round(100 * got / total, 1)
    fmt_got = sum({"pass": 1.0, "warn": 0.6}.get(c.status, 0.0) for c in fmt)
    return round(100 * (0.75 * got / total + 0.25 * fmt_got / len(fmt)), 1)


def check_pdf(pdf: bytes, resume: TailoredResume) -> ATSReport:
    doc = extract_pdf(pdf)
    parsed = parse_resume(doc)
    fields = compare_fields(parsed, doc, resume)
    fmt = format_checks(doc, resume, "pdf")
    return ATSReport(extractor="pymupdf", document_kind="pdf", score=_score(fields, fmt), page_count=doc.page_count,
                     fields=fields, checks=fmt, extracted_text_sample=doc.text[:1500])


def check_docx(docx_bytes: bytes, resume: TailoredResume) -> ATSReport:
    doc = extract_docx(docx_bytes)
    parsed = parse_resume(doc)
    fields = compare_fields(parsed, doc, resume)
    fmt = format_checks(doc, resume, "docx")
    return ATSReport(extractor="python-docx", document_kind="docx", score=_score(fields, fmt), fields=fields,
                     checks=fmt, extracted_text_sample=doc.text[:1500])


def pdftotext_available() -> bool:
    return shutil.which("pdftotext") is not None


def check_pdf_with_pdftotext(pdf: bytes, resume: TailoredResume) -> ATSReport | None:
    """Second, independent extraction engine (poppler). Runs locally; nothing leaves the machine."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-layout", "-enc", "UTF-8", "-", "-"], input=pdf, capture_output=True,
                             timeout=30, check=True).stdout.decode("utf-8", errors="replace")
    except (subprocess.SubprocessError, OSError):
        return None
    lines = []
    for raw in clean_text(out).splitlines():
        if raw.strip():
            lines.append(raw.rstrip())
    doc = extract_text("\n".join(lines).encode("utf-8"))
    # pdftotext keeps the bullet glyph; the plain-text extractor already strips it.
    doc.kind = "pdf"
    parsed = parse_resume(doc)
    fields = compare_fields(parsed, doc, resume)
    return ATSReport(extractor="pdftotext (poppler)", document_kind="pdf", score=_score(fields, []), fields=fields,
                     checks=[], extracted_text_sample=doc.text[:1500])
