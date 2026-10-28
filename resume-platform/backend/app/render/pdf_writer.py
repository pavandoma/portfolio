"""Deterministic, ATS-friendly PDF rendering with ReportLab.

Design choices that keep the document parseable and human-looking:
  * single column, standard headings, real selectable text, no images, icons or skill bars;
  * name, target title and contact details in the page body (never in a page header/footer);
  * a conventional Word-style layout: centred name, bold section headings with a thin rule,
    right-aligned dates and locations, simple round bullets;
  * embedded, metric-compatible fonts (Carlito ~ Calibri, Liberation Serif ~ Times New Roman)
    so text extracts cleanly; falls back to the PDF base-14 fonts if they are missing.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.resume import TailoredResume

FONT_DIRS = [
    os.environ.get("RIP_FONT_DIR", ""),
    str(Path(__file__).resolve().parent.parent / "data" / "fonts"),
    "/usr/share/fonts/truetype/crosextra",
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/liberation2",
    "/usr/share/fonts/liberation",
    "/usr/share/fonts/crosextra",
]
FAMILIES = {
    "sans": ("Carlito", ["Carlito-Regular.ttf", "Carlito-Bold.ttf", "Carlito-Italic.ttf", "Carlito-BoldItalic.ttf"],
             ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique")),
    "serif": ("LiberationSerif", ["LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf",
                                  "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf"],
              ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic")),
}


@dataclass(frozen=True)
class FontSet:
    regular: str
    bold: str
    italic: str
    bold_italic: str
    embedded: bool


def _find(fname: str) -> str | None:
    for d in FONT_DIRS:
        if d and (Path(d) / fname).exists():
            return str(Path(d) / fname)
    return None


@lru_cache
def get_fonts(family: str) -> FontSet:
    base, files, fallback = FAMILIES.get(family, FAMILIES["sans"])
    paths = [_find(f) for f in files]
    if all(paths):
        names = [f"{base}", f"{base}-Bold", f"{base}-Italic", f"{base}-BoldItalic"]
        for n, p in zip(names, paths, strict=True):
            if n not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(n, p))
        pdfmetrics.registerFontFamily(base, normal=names[0], bold=names[1], italic=names[2], boldItalic=names[3])
        return FontSet(*names, embedded=True)
    return FontSet(*fallback, embedded=False)


class HRule(Flowable):
    def __init__(self, width: float, thickness: float = 0.6, space_before: float = 1.0):
        super().__init__()
        self.width, self.thickness, self.space_before = width, thickness, space_before

    def wrap(self, availWidth, availHeight):
        return availWidth, self.thickness + self.space_before

    def draw(self):
        self.canv.setStrokeColor(colors.black)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


def _p(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def build_story(resume: TailoredResume, width: float, fonts: FontSet, size: float):
    lead = size * 1.24
    st = {
        "name": ParagraphStyle("name", fontName=fonts.bold, fontSize=size + 6.5, leading=size + 9, alignment=TA_CENTER),
        "title": ParagraphStyle("title", fontName=fonts.regular, fontSize=size + 1.5, leading=size + 4, alignment=TA_CENTER),
        "contact": ParagraphStyle("contact", fontName=fonts.regular, fontSize=size - 0.5, leading=size + 2,
                                  alignment=TA_CENTER),
        "body": ParagraphStyle("body", fontName=fonts.regular, fontSize=size, leading=lead, alignment=TA_LEFT),
        "heading": ParagraphStyle("heading", fontName=fonts.bold, fontSize=size + 0.5, leading=size + 2,
                                  spaceBefore=size * 0.75, spaceAfter=0),
        "left": ParagraphStyle("left", fontName=fonts.regular, fontSize=size, leading=lead),
        "right": ParagraphStyle("right", fontName=fonts.regular, fontSize=size, leading=lead, alignment=TA_RIGHT),
        "bullet": ParagraphStyle("bullet", fontName=fonts.regular, fontSize=size, leading=lead, leftIndent=13,
                                 bulletIndent=3, spaceBefore=0.6, bulletFontName=fonts.regular),
    }
    story: list = []
    story.append(Paragraph(_p(resume.header.name.upper()), st["name"]))
    story.append(Paragraph(_p(resume.header.target_title), st["title"]))
    contact_parts = []
    for item, link in zip(resume.header.contact, resume.header.links + [""] * len(resume.header.contact), strict=False):
        contact_parts.append(f'<a href="{_p(link)}">{_p(item)}</a>' if link else _p(item))
    story.append(Paragraph("  |  ".join(contact_parts), st["contact"]))
    story.append(Spacer(1, size * 0.5))

    def heading(text: str):
        return [Paragraph(_p(text.upper()), st["heading"]), HRule(width), Spacer(1, size * 0.3)]

    def two_col(left_html: str, right_text: str | None, left_style="left"):
        if not right_text:
            return Paragraph(left_html, st[left_style])
        t = Table([[Paragraph(left_html, st[left_style]), Paragraph(_p(right_text), st["right"])]],
                  colWidths=[width * 0.72, width * 0.28])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        return t

    def bullets(items):
        return [Paragraph(_p(b.text), st["bullet"], bulletText="•") for b in items]

    for section in resume.section_order:
        if section == "summary" and resume.summary:
            story.append(Paragraph(_p(" ".join(s.text for s in resume.summary)), st["body"]))
        elif section == "skills" and resume.skills:
            story += heading("Skills")
            for line in resume.skills:
                story.append(Paragraph(f"<b>{_p(line.category)}:</b> {_p(', '.join(line.items))}", st["body"]))
        elif section == "experience" and resume.experience:
            story += heading("Professional Experience")
            for i, e in enumerate(resume.experience):
                block = [two_col(f"<b>{_p(e.title)}</b>", e.location), two_col(_p(e.organization), e.date_range)]
                block += bullets(e.bullets[:1])
                story.append(KeepTogether(block))
                story += bullets(e.bullets[1:])
                if i < len(resume.experience) - 1:
                    story.append(Spacer(1, size * 0.45))
        elif section == "projects" and resume.projects:
            all_academic = all(p.descriptor == "Academic project" for p in resume.projects)
            story += heading("Academic Projects" if all_academic else "Projects")
            for i, p in enumerate(resume.projects):
                right = p.date_range if all_academic else " | ".join(x for x in (p.descriptor, p.date_range) if x)
                block = [two_col(f"<b>{_p(p.name)}</b>", right or None)] + bullets(p.bullets[:1])
                story.append(KeepTogether(block))
                story += bullets(p.bullets[1:])
                if i < len(resume.projects) - 1:
                    story.append(Spacer(1, size * 0.3))
        elif section == "education" and resume.education:
            story += heading("Education")
            for i, ed in enumerate(resume.education):
                degree = ed.degree + (f" (GPA: {ed.gpa})" if ed.gpa else "")
                story.append(KeepTogether([two_col(f"<b>{_p(ed.institution)}</b>", ed.location),
                                           two_col(_p(degree), ed.date)]))
                if i < len(resume.education) - 1:
                    story.append(Spacer(1, size * 0.3))
        elif section == "certifications" and resume.certifications:
            story += heading("Certifications")
            for c in resume.certifications:
                label = c.name + (f" ({c.detail})" if c.detail else "")
                t = Table([[Paragraph(_p(label), st["bullet"], bulletText="•"), Paragraph(_p(c.date), st["right"])]],
                          colWidths=[width * 0.8, width * 0.2])
                t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                       ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                story.append(t)
    return story


def render_pdf(resume: TailoredResume, *, page_size: str = "letter") -> bytes:
    fonts = get_fonts(resume.layout.font_family)
    size = resume.layout.body_font_size
    margin = resume.layout.margin_in * inch
    pagesize = A4 if page_size.lower() == "a4" else LETTER
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=margin, rightMargin=margin,
                            topMargin=margin * 0.85, bottomMargin=margin * 0.85,
                            title=f"{resume.header.name} - Resume", author=resume.header.name,
                            subject=resume.header.target_title, creator=resume.header.name)
    # Frames have 6 pt padding on each side; tables and rules must use the inner width.
    width = doc.width - 12
    doc.build(build_story(resume, width, fonts, size))
    return buf.getvalue()


def page_count(pdf: bytes) -> int:
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        return d.page_count


def last_page_fill(pdf: bytes) -> float:
    """Fraction of the last page's height used by text (to detect a nearly empty overflow page)."""
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        page = d[-1]
        blocks = [b for b in page.get_text("blocks") if b[4].strip()]
        if not blocks:
            return 0.0
        return max(b[3] for b in blocks) / page.rect.height
