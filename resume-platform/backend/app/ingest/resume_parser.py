"""Layout-aware resume parser.

Turns extracted lines into sections and entries. It is deliberately conservative: it keeps
the original wording of every line, records where each item came from, and reports what it
could not interpret instead of guessing. The same parser is used to read back generated
resumes for the ATS parsing check, so it doubles as an independent extraction test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.dates import find_date_range, find_single_date
from app.core.taxonomy import get_taxonomy
from app.core.text import collapse_ws
from app.ingest.extract import DocLine, ExtractedDocument

SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["summary", "professional summary", "profile", "professional profile", "about", "about me",
                "objective", "career objective", "overview", "career summary", "summary of qualifications"],
    "skills": ["skills", "technical skills", "core competencies", "key skills", "skills and tools",
               "skills & tools", "technologies", "technical expertise", "expertise", "tools and technologies",
               "skills & technologies", "competencies", "technical proficiencies"],
    "experience": ["experience", "professional experience", "work experience", "employment", "employment history",
                   "relevant experience", "work history", "industry experience", "internships", "internship experience",
                   "research experience", "professional background"],
    "projects": ["projects", "academic projects", "personal projects", "selected projects", "key projects",
                 "relevant projects", "technical projects", "research projects", "project experience", "projects & research"],
    "education": ["education", "academic background", "academic qualifications", "education and training"],
    "certifications": ["certifications", "certificates", "licenses & certifications", "licenses and certifications",
                       "certifications & training", "certifications and training", "courses", "training",
                       "professional certifications", "certification"],
    "other": ["awards", "honors", "honors & awards", "publications", "leadership", "volunteer", "volunteering",
              "activities", "interests", "languages", "achievements", "extracurricular activities"],
}
_HEADING_INDEX = {alias: key for key, aliases in SECTION_ALIASES.items() for alias in aliases}

TITLE_WORDS = re.compile(
    r"\b(engineer|engineering lead|analyst|developer|scientist|intern|internship|assistant|manager|lead|consultant|"
    r"specialist|associate|researcher|architect|administrator|coordinator|director|officer|technician|fellow|"
    r"programmer|designer|strategist|head|president|founder|co-founder|owner|tutor|instructor|trainee|apprentice|"
    r"representative|executive|advisor|teaching assistant|research assistant|graduate assistant)\b",
    re.IGNORECASE,
)
DEGREE_WORDS = re.compile(
    r"\b(bachelor'?s?|master'?s?|b\.?\s?tech|m\.?\s?tech|b\.?\s?e\.?|m\.?\s?e\.?|b\.?s\.?c?|m\.?s\.?c?|b\.?a\.?|m\.?a\.?|"
    r"mba|ph\.?\s?d|doctorate|associate'?s? degree|diploma|m\.?eng|b\.?eng|engineering science)\b",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(
    r"^(?:remote|hybrid|on-?site|[A-Z][A-Za-z.\- ]+,\s*(?:[A-Z]{2}|[A-Z][A-Za-z ]+))(?:\s*\(.*\))?$"
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s|,;]+|(?:linkedin\.com|github\.com)/[^\s|,;]+", re.IGNORECASE)


@dataclass
class ParsedBullet:
    text: str
    line_index: int
    page: int


@dataclass
class ParsedEntry:
    header: list[str]
    title: str = ""
    organization: str = ""
    location: str | None = None
    date_text: str = ""
    start: str | None = None
    end: str | None = None
    bullets: list[ParsedBullet] = field(default_factory=list)
    line_index: int = 0
    page: int = 0
    extra: dict = field(default_factory=dict)


@dataclass
class ParsedSection:
    key: str
    heading: str
    lines: list[DocLine]


@dataclass
class ParsedResume:
    name: str = ""
    headline: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    location: str | None = None
    contact_line: str = ""
    summary: str | None = None
    skills: list[dict] = field(default_factory=list)
    experience: list[ParsedEntry] = field(default_factory=list)
    projects: list[ParsedEntry] = field(default_factory=list)
    education: list[ParsedEntry] = field(default_factory=list)
    certifications: list[ParsedEntry] = field(default_factory=list)
    sections: list[ParsedSection] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def section_order(self) -> list[str]:
        return [s.key for s in self.sections]


def classify_heading(line: DocLine) -> str | None:
    if line.is_bullet or len(line.segments) > 1:
        return None
    text = line.text.strip().rstrip(":").strip()
    if not text or len(text) > 45:
        return None
    key = re.sub(r"\s+", " ", re.sub(r"[^a-z& ]", "", text.lower())).strip()
    if key in _HEADING_INDEX:
        return _HEADING_INDEX[key]
    return None


def _looks_like_unknown_heading(line: DocLine) -> bool:
    t = line.text.strip()
    return (
        not line.is_bullet and line.bold and t.isupper() and 1 <= len(t.split()) <= 4
        and not any(ch.isdigit() for ch in t) and len(line.segments) == 1
    )


def smart_title(text: str) -> str:
    """Convert ALL-CAPS headings to title case, keeping acronyms such as RAG, NLP, AWS."""
    if not text.isupper():
        return text
    tax = get_taxonomy()
    small = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "via", "with"}
    out = []
    for i, word in enumerate(re.split(r"(\s+|-|/|\()", text)):
        if not word or word.isspace() or word in "-/(":
            out.append(word)
            continue
        core = word.strip("(),.&")
        known = None
        for node in tax.nodes.values():
            for form in [node.name, *node.aliases]:
                if form.upper() == core and any(c.isupper() for c in form[1:]):
                    known = form
                    break
            if known:
                break
        if known:
            out.append(word.replace(core, known))
        elif core in {"AI", "ML", "NLP", "LLM", "API", "SQL", "ETL", "BI", "KPI", "USA", "UK", "US", "SUNY"}:
            out.append(word)
        elif core.lower() in small and i > 0:
            out.append(word.lower())
        else:
            out.append(word[:1] + word[1:].lower() if word[:1] != "(" else "(" + word[1:2] + word[2:].lower())
    return "".join(out)


def _split_entry_header(texts: list[str]) -> dict:
    """Assign title / organisation / location / dates from 1-3 header strings."""
    result: dict = {"title": "", "organization": "", "location": None, "date_text": "", "start": None, "end": None}
    leftovers: list[str] = []
    for raw in texts:
        for part in re.split(r"\s+\|\s+|\s{3,}|\t", raw):
            part = part.strip(" |")
            if not part:
                continue
            dr = find_date_range(part)
            if dr and not result["date_text"]:
                result["start"], result["end"], result["date_text"] = dr
                rest = collapse_ws(part.replace(dr[2], " ")).strip(" ,|()")
                if rest:
                    leftovers.append(rest)
                continue
            sd = find_single_date(part)
            if sd and not result["date_text"] and len(sd[1]) >= len(part) - 2:
                result["end"], result["date_text"] = sd[0], sd[1]
                continue
            if LOCATION_RE.match(part) and not TITLE_WORDS.search(part) and result["location"] is None and len(part) < 40:
                result["location"] = part
                continue
            leftovers.append(part)
    titles = [p for p in leftovers if TITLE_WORDS.search(p)]
    others = [p for p in leftovers if not TITLE_WORDS.search(p)]
    if titles and others:
        result["title"], result["organization"] = titles[0], others[0]
    elif len(leftovers) >= 2:
        result["title"], result["organization"] = leftovers[0], leftovers[1]
    elif len(leftovers) == 1:
        one = leftovers[0]
        m = re.match(r"^(?P<t>.+?)(?:,\s+|\s+at\s+|\s+@\s+)(?P<o>[^,]+)$", one)
        if m and TITLE_WORDS.search(m.group("t")):
            result["title"], result["organization"] = m.group("t"), m.group("o")
        else:
            result["title"] = one
    return result


class _Cursor:
    """Groups the lines of a section into entries (header lines followed by bullets)."""

    def __init__(self, lines: list[DocLine]):
        self.lines = lines

    def entries(self, *, bullets_only_continuation: bool = True) -> list[tuple[list[DocLine], list[list[DocLine]]]]:
        groups: list[tuple[list[DocLine], list[list[DocLine]]]] = []
        header: list[DocLine] = []
        bullets: list[list[DocLine]] = []
        last_bullet_x: float | None = None
        for line in self.lines:
            if line.is_bullet:
                bullets.append([line])
                last_bullet_x = line.x0
                continue
            if bullets and self._is_continuation(line, bullets[-1][-1], last_bullet_x):
                bullets[-1].append(line)
                continue
            if bullets:
                groups.append((header, bullets))
                header, bullets = [], []
            header.append(line)
        if header or bullets:
            groups.append((header, bullets))
        return groups

    @staticmethod
    def _is_continuation(line: DocLine, prev: DocLine, bullet_x: float | None) -> bool:
        if line.bold or find_date_range(line.text):
            return False
        if line.right and (find_single_date(line.right) or LOCATION_RE.match(line.right)):
            return False
        if prev.x0 > 0 or line.x0 > 0:  # real layout coordinates available
            return bullet_x is not None and line.x0 >= bullet_x + 3
        text = line.text
        return bool(text[:1].islower()) or not prev.text.rstrip().endswith((".", "!", "?"))


def _join_bullet(lines: list[DocLine]) -> str:
    text = ""
    for ln in lines:
        part = ln.text.strip()
        if text.endswith("-") and part[:1].islower():
            text = text[:-1] + part
        else:
            text = f"{text} {part}" if text else part
    return collapse_ws(text)


def _split_skill_items(items_text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in items_text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;|•·" and depth == 0:
            if cur.strip():
                out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [o.strip(" .") for o in out if o.strip(" .")]


def parse_skills(lines: list[DocLine]) -> list[dict]:
    rows: list[dict] = []
    for line in lines:
        text = line.text.strip()
        m = re.match(r"^(?P<cat>[^:]{2,45}):\s*(?P<items>.*)$", text)
        if m and not URL_RE.search(m.group("cat")):
            rows.append({"category": m.group("cat").strip(), "items_text": m.group("items"), "line_index": line.index,
                         "page": line.page, "raw": text})
        elif rows and (rows[-1]["items_text"].rstrip().endswith(",") or not line.bold):
            rows[-1]["items_text"] += " " + text
            rows[-1]["raw"] += " " + text
        else:
            rows.append({"category": None, "items_text": text, "line_index": line.index, "page": line.page, "raw": text})
    for row in rows:
        expanded: list[dict] = []
        for item in _split_skill_items(row["items_text"]):
            m = re.match(r"^(?P<base>[^()]+)\((?P<inner>[^()]+)\)$", item)
            if m and "," in m.group("inner"):
                base = m.group("base").strip()
                expanded.append({"display": base, "group": item})
                for child in _split_skill_items(m.group("inner")):
                    expanded.append({"display": child, "group": item, "prefix": base})
            else:
                expanded.append({"display": item, "group": None})
        row["items"] = expanded
    return rows


def parse_resume(doc: ExtractedDocument) -> ParsedResume:
    result = ParsedResume()
    # PDFs have no structural header/footer, so every line is parsed; text in the extreme
    # margins is reported by the ATS check instead. (DOCX header/footer text is never in doc.lines.)
    body = doc.lines
    # --- split into sections
    first_heading = None
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None
    for i, line in enumerate(body):
        key = classify_heading(line)
        if key is None and current is not None and _looks_like_unknown_heading(line) and current.key in ("other",):
            key = "other"
        if key:
            if first_heading is None:
                first_heading = i
            current = ParsedSection(key=key, heading=line.text.strip(), lines=[])
            sections.append(current)
        elif current is not None:
            current.lines.append(line)
    result.sections = sections
    header_lines = body[: first_heading if first_heading is not None else min(4, len(body))]
    _parse_header(header_lines, doc, result)

    for sec in sections:
        if sec.key == "summary":
            text = collapse_ws(" ".join(ln.text for ln in sec.lines))
            result.summary = text or None
        elif sec.key == "skills":
            result.skills.extend(parse_skills(sec.lines))
        elif sec.key in ("experience", "projects"):
            for header, bullets in _Cursor(sec.lines).entries():
                if not header and bullets and (result.experience if sec.key == "experience" else result.projects):
                    target = (result.experience if sec.key == "experience" else result.projects)[-1]
                    target.bullets.extend(ParsedBullet(_join_bullet(b), b[0].index, b[0].page) for b in bullets)
                    continue
                header_texts = [h.text if len(h.segments) == 1 else "   ".join(s.text for s in h.segments) for h in header]
                entry = ParsedEntry(header=[h.text for h in header],
                                    line_index=header[0].index if header else (bullets[0][0].index if bullets else 0),
                                    page=header[0].page if header else 0)
                if sec.key == "experience":
                    entry.__dict__.update(_split_entry_header(header_texts))
                else:
                    _fill_project_header(entry, header, header_texts)
                entry.bullets = [ParsedBullet(_join_bullet(b), b[0].index, b[0].page) for b in bullets]
                entry.extra["section_heading"] = sec.heading
                (result.experience if sec.key == "experience" else result.projects).append(entry)
        elif sec.key == "education":
            result.education.extend(_parse_education(sec.lines))
        elif sec.key == "certifications":
            for line in sec.lines:
                text = line.text
                parts = [s.text for s in line.segments]
                date_text, end = "", None
                if len(parts) > 1 and find_single_date(parts[-1]):
                    sd = find_single_date(parts[-1])
                    end, date_text = sd
                    name_part = collapse_ws(" ".join(parts[:-1]))
                else:
                    sd = find_single_date(text)
                    name_part = text
                    if sd and text.rstrip().endswith(sd[1].strip()):
                        end, date_text = sd
                        name_part = text[: text.rfind(sd[1])].strip(" -|,")
                if not line.is_bullet and result.certifications and not date_text and line.text[:1].islower():
                    result.certifications[-1].title += " " + text
                    continue
                entry = ParsedEntry(header=[text], title=name_part, date_text=date_text, end=end,
                                    line_index=line.index, page=line.page)
                result.certifications.append(entry)
    if not sections:
        result.warnings.append("No standard section headings were found.")
    return result


def _fill_project_header(entry: ParsedEntry, header: list[DocLine], texts: list[str]) -> None:
    joined = texts[0] if texts else ""
    parts = [p.strip() for p in re.split(r"\s+\|\s+|\s{3,}|\t", joined) if p.strip()]
    name = parts[0] if parts else ""
    for p in parts[1:] + texts[1:]:
        dr = find_date_range(p)
        sd = find_single_date(p) if not dr else None
        if dr:
            entry.start, entry.end, entry.date_text = dr
        elif sd and len(sd[1]) >= len(p) - 2:
            entry.end, entry.date_text = sd
        elif URL_RE.search(p):
            entry.extra["url"] = URL_RE.search(p).group(0)
        else:
            entry.extra.setdefault("descriptors", []).append(p)
    m = re.match(r"^(?P<n>.+?)\s*\((?P<sub>[^()]+)\)\s*$", name)
    if m:
        entry.title, entry.extra["subtitle"] = m.group("n").strip(), m.group("sub").strip()
    else:
        entry.title = name
    for h in header:
        for link in h.links:
            entry.extra.setdefault("links", []).append(link)


def _parse_education(lines: list[DocLine]) -> list[ParsedEntry]:
    entries: list[ParsedEntry] = []
    current: ParsedEntry | None = None
    for line in lines:
        parts = [s.text for s in line.segments]
        text = line.text
        main = collapse_ws(" ".join(parts[:-1])) if len(parts) > 1 else text
        right = parts[-1] if len(parts) > 1 else None
        is_degree = bool(DEGREE_WORDS.search(main))
        gpa = re.search(r"(?:c?gpa|grade)[:\s]*([0-9.]+(?:\s*/\s*[0-9.]+)?)", text, re.IGNORECASE)
        if is_degree:
            if current is None or current.extra.get("degree"):
                current = ParsedEntry(header=[], line_index=line.index, page=line.page)
                entries.append(current)
            current.extra["degree"] = re.sub(r"\(?\s*(?:c?gpa|grade)[:\s]*[0-9.]+(?:\s*/\s*[0-9.]+)?\)?", "", main,
                                             flags=re.IGNORECASE).strip(" .,|")
            current.header.append(text)
        else:
            if current is None or current.organization:
                current = ParsedEntry(header=[], line_index=line.index, page=line.page)
                entries.append(current)
            current.organization = main.strip(" ,|")
            current.header.append(text)
        if gpa:
            current.extra["gpa"] = gpa.group(1)
        if right:
            dr = find_date_range(right)
            sd = find_single_date(right)
            if dr:
                current.start, current.end, current.date_text = dr
            elif sd and len(sd[1]) >= len(right) - 3:
                current.end, current.date_text = sd
            elif LOCATION_RE.match(right) or "," in right:
                current.location = right
        else:
            dr = find_date_range(text)
            sd = find_single_date(text)
            if dr and not current.date_text:
                current.start, current.end, current.date_text = dr
            elif sd and not current.date_text:
                current.end, current.date_text = sd
    for e in entries:
        e.title = e.extra.get("degree", "")
    return entries


def _parse_header(lines: list[DocLine], doc: ExtractedDocument, result: ParsedResume) -> None:
    if not lines:
        result.warnings.append("No header block found.")
        return
    name_line = max(lines[:3], key=lambda ln: ln.size)
    result.name = collapse_ws(name_line.text)
    contact_bits: list[str] = []
    for line in lines:
        if line is name_line:
            continue
        text = line.text
        has_contact = bool(EMAIL_RE.search(text) or PHONE_RE.search(text) or URL_RE.search(text)
                           or re.search(r"\blinked\s?in\b|\bgithub\b", text, re.IGNORECASE))
        if has_contact:
            contact_bits.append(text)
            result.emails += [e for e in EMAIL_RE.findall(text) if e not in result.emails]
            result.phones += [p.strip() for p in PHONE_RE.findall(text) if p.strip() not in result.phones]
            result.urls += [u.rstrip(".") for u in URL_RE.findall(text) if u not in result.urls]
            for chunk in re.split(r"\s*[|•·]\s*", text):
                chunk = chunk.strip()
                if LOCATION_RE.match(chunk) and not EMAIL_RE.search(chunk) and result.location is None:
                    result.location = chunk
        elif result.headline is None and len(text) < 80 and not find_date_range(text):
            result.headline = text.strip()
        elif LOCATION_RE.match(text.strip()):
            result.location = text.strip()
    for lk in doc.links:
        uri = lk["uri"]
        if uri.startswith("mailto:"):
            addr = uri[7:]
            if addr and addr not in result.emails:
                result.emails.append(addr)
        elif uri not in result.urls and (lk.get("page", 0) == 0):
            # Only links located in the header block count as profile links.
            rect = lk.get("rect")
            if rect is None or any(abs(rect[1] - ln.y) < 14 for ln in lines):
                result.urls.append(uri)
    result.contact_line = " | ".join(contact_bits)
