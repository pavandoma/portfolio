"""Deterministic job-description analysis.

Every requirement keeps the posting's original wording. Its category (mandatory / preferred /
responsibility / context) records *why* it was classified that way: an explicit cue word in
the line, the section heading it sits under, or an inference. The posting is untrusted
input: lines that look like instructions to an AI system are reported and ignored.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.core.security import detect_injection
from app.core.taxonomy import get_taxonomy
from app.core.text import clean_text, collapse_ws, sentence_split, strip_bullet
from app.ingest.resume_parser import TITLE_WORDS
from app.schemas.job import AuthorizationRequirement, JobAnalysis, RankedSkill, Requirement, SkillMention

PARSER_VERSION = "jd-1.0"

SECTION_CUES: list[tuple[str, str]] = [
    # (regex on the normalised heading, section category)
    (r"preferred|nice to have|nice-to-have|bonus|plus(es)?$|desired|good to have|would be great|ideal(ly)?|extra credit|stand out", "preferred"),
    (r"requirements?|qualifications?|what you('ll)? (need|bring)|what we('re)? looking for|must have|must-have|"
     r"you (have|bring|are)|who you are|required skills|skills (and|&) experience|about you|your background|"
     r"what you need|minimum|basic qualifications|essential", "mandatory"),
    (r"responsibilit|what you('ll)? do|the role|your role|duties|day[- ]to[- ]day|your impact|in this role|"
     r"what you will do|key accountabilities|the opportunity|the job|job description|role overview", "responsibility"),
    (r"^about\b|benefits|perks|compensation|salary|pay range|equal opportunity|eeo|"
     r"our values|why (join|work)|culture|how to apply|location|work environment|diversity", "context"),
]
MANDATORY_CUE = re.compile(
    r"\b(required|requirement|must|need to have|needs to have|minimum of|at least \d|essential|mandatory|you have)\b", re.I
)
PREFERRED_CUE = re.compile(
    r"\b(preferred|nice to have|nice-to-have|a plus|is a plus|are a plus|bonus|ideally|desirable|desired|"
    r"familiarity with .* (?:is )?helpful|helpful|advantageous|would be great)\b", re.I
)
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:(?:-|to|–)\s*(\d{1,2})\s*)?\+?\s*(?:years?|yrs?)\b", re.I)
DEGREE_RE = re.compile(
    r"\b(bachelor'?s?|master'?s?|ph\.?\s?d|doctorate|b\.?\s?s\.?|m\.?\s?s\.?|b\.?\s?a\.?|mba|degree|bs/ms|ms/phd|"
    r"undergraduate|graduate degree)\b", re.I
)
CERT_RE = re.compile(r"\b(certified|certification|certificate|license[d]?)\b", re.I)
AUTH_RE = re.compile(
    r"\b(sponsor\w*|visa|authori[sz]ed to work|work authori[sz]ation|u\.?s\.? citizen\w*|citizenship|green card|"
    r"permanent resident|us person|itar|export control)\b", re.I
)
CLEARANCE_RE = re.compile(r"\b(security clearance|clearance|ts/sci|top secret|secret clearance|public trust)\b", re.I)
SOFT_RE = re.compile(
    r"\b(communication|communicate|collaborat\w+|team player|teamwork|stakeholders?|self-starter|ownership|"
    r"curious|curiosity|attention to detail|problem[- ]solving|presentation|interpersonal|mentor\w*|leadership)\b", re.I
)
ANY_OF_RE = re.compile(r"\b(or|such as|e\.g\.|eg\.|for example|including|one or more of|at least one of|any of)\b|/", re.I)
DOMAINS = {
    "banking": r"\bbank(?:ing)?\b", "financial services": r"\bfinancial services|fintech|finance\b",
    "healthcare": r"\bhealth ?care|clinical|patient|hospital|medical\b", "insurance": r"\binsurance|insurtech\b",
    "e-commerce": r"\be-?commerce|online retail|marketplace\b", "retail": r"\bretail\b",
    "marketing": r"\bmarketing|advertising|adtech|campaigns?\b", "logistics": r"\blogistics|supply chain|warehouse operations\b",
    "manufacturing": r"\bmanufacturing\b", "telecommunications": r"\btelecom\w*\b", "government": r"\bgovernment|public sector|federal\b",
    "education": r"\bedtech|higher education|universit(y|ies)\b", "cybersecurity": r"\bcyber ?security|infosec\b",
    "gaming": r"\bgaming|video games?\b", "energy": r"\benergy|utilities|oil and gas\b",
    "pharma/biotech": r"\bpharma\w*|biotech\w*|life sciences\b", "saas": r"\bsaas|b2b software\b",
}
LABELLED_FIELD_RE = re.compile(
    r"^\s*(job title|title|position|role|company|employer|organization|location|employment type|job type|"
    r"workplace type|work arrangement|work model|seniority|level)\s*[:\-–]\s*(.+)$", re.I
)
WORK_ARRANGEMENT = [
    (re.compile(r"\bhybrid\b|\d\s*days? (?:a week |per week )?(?:in|on)[- ](?:the )?(?:office|site)", re.I), "hybrid"),
    (re.compile(r"\b(fully remote|100% remote|remote[- ]first|remote(?: \(|,| -| –| role| position| within| in the| us| eligible)|work from home|wfh)\b", re.I), "remote"),
    (re.compile(r"\b(on-?site|in-?office|in office|in-person)\b", re.I), "onsite"),
]
US_STATE = (r"AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|"
            r"OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC")
COUNTRIES = (r"USA|United States|US|Canada|United Kingdom|UK|India|Germany|France|Ireland|Netherlands|Australia|"
             r"Singapore|Spain|Poland|Mexico|Brazil|Japan|Remote")
LOCATION_RE = re.compile(rf"\b([A-Z][a-zA-Z.]+(?:\s[A-Z][a-zA-Z.]+){{0,2}}),\s*({US_STATE}|{COUNTRIES})\b")
BENEFITS_HEADING = re.compile(r"benefit|perk|compensation|salary|pay range|equal opportunity|eeo|diversity|how to apply", re.I)
HEADING_LINE = re.compile(r"^(?:#{1,4}\s*)?(?P<h>[A-Za-z][A-Za-z0-9 &'’/,()\-]{1,60}?)\s*:?\s*$")


def _section_of(heading: str) -> str | None:
    h = re.sub(r"[^a-z0-9 /&'-]", "", heading.lower()).strip()
    if not h or len(h.split()) > 8:
        return None
    for rx, cat in SECTION_CUES:
        if re.search(rx, h):
            return cat
    return None


def _is_heading(raw_line: str, next_is_list: bool) -> str | None:
    line = raw_line.strip()
    if not line or len(line) > 70:
        return None
    if line.startswith("#"):
        return line.lstrip("# ").rstrip(":").strip()
    m = HEADING_LINE.match(line)
    if not m:
        return None
    text = m.group("h").strip()
    if line.endswith(":") or (text.isupper() and len(text) > 3) or (next_is_list and len(text.split()) <= 6):
        return text
    if _section_of(text) and len(text.split()) <= 6 and not text.endswith("."):
        return text
    return None


def _seniority(title: str, min_years: float | None) -> str:
    t = title.lower()
    if re.search(r"\bintern(ship)?\b|\bco-?op\b", t):
        return "intern"
    if re.search(r"\b(principal|distinguished)\b", t):
        return "principal"
    if re.search(r"\bstaff\b", t):
        return "staff"
    if re.search(r"\b(director|head of|vp|manager)\b", t):
        return "manager"
    if re.search(r"\b(senior|sr\.?|iii|iv)\b", t):
        return "senior"
    if re.search(r"\blead\b", t):
        return "lead"
    if re.search(r"\b(junior|jr\.?|entry|associate|new grad|graduate|early career|i)\b", t):
        return "entry"
    if re.search(r"\bii\b", t):
        return "mid"
    if min_years is not None:
        if min_years <= 2:
            return "entry"
        if min_years <= 5:
            return "mid"
        return "senior"
    return "unknown"


def _guess_title(lines: list[str]) -> tuple[str, str]:
    for line in lines[:8]:
        m = LABELLED_FIELD_RE.match(line)
        if m and m.group(1).lower() in ("job title", "title", "position", "role"):
            return collapse_ws(m.group(2)), "labelled"
    for line in lines[:5]:
        text = strip_bullet(line)[0].strip().lstrip("#").strip()
        if 1 <= len(text.split()) <= 10 and TITLE_WORDS.search(text) and not text.endswith(".") and ":" not in text:
            return collapse_ws(re.sub(r"\s*[-–|]\s*(remote|hybrid|on-?site).*$", "", text, flags=re.I)), "first_line"
    joined = " ".join(lines[:15])
    m = re.search(r"(?:hiring|seeking|looking for|recruiting)\s+(?:an?\s+)?(?:talented\s+|motivated\s+)?"
                  r"(?P<t>[A-Z][\w/&\- ]{2,60}?(?:engineer|analyst|developer|scientist|manager|specialist|architect|lead|consultant))",
                  joined)
    if m:
        return collapse_ws(m.group("t")), "pattern"
    return "", "unknown"


def _guess_company(lines: list[str]) -> str | None:
    for line in lines[:15]:
        m = LABELLED_FIELD_RE.match(line)
        if m and m.group(1).lower() in ("company", "employer", "organization"):
            return collapse_ws(m.group(2))
    for line in lines:
        m = re.match(r"^\s*#*\s*[Aa]bout\s+(?!us\b|the\b|you\b|this\b|our\b)(?P<c>[A-Z][\w&.\- ]{1,40}?)\s*:?\s*$", line)
        if m:
            return m.group("c").strip()
    joined = " ".join(lines[:20])
    m = re.search(r"\b(?:at|join)\s+(?P<c>[A-Z][A-Za-z0-9&.\-]+(?:\s[A-Z][A-Za-z0-9&.\-]+){0,3})(?=[,.!]|\s(?:is|we|and|as|to|where))",
                  joined)
    if m and not TITLE_WORDS.search(m.group("c")):
        return m.group("c").strip()
    for line in lines[:20]:
        m = re.match(r"^(?P<c>[A-Z][A-Za-z0-9&.\-]+(?:\s[A-Z][A-Za-z0-9&.\-]+){0,3}) (?:is|are) "
                     r"(?:a|an|the|hiring|building|looking|seeking|on a mission)\b", line.strip())
        if m and not TITLE_WORDS.search(m.group("c")):
            return m.group("c").strip()
    return None


def _requirement_kind(text: str, section: str | None, skills: list[SkillMention]) -> str:
    if AUTH_RE.search(text):
        return "work_authorization"
    if CLEARANCE_RE.search(text):
        return "clearance"
    if YEARS_RE.search(text) and re.search(r"experience|years? (of|in|with|working)", text, re.I):
        return "experience_years"
    if DEGREE_RE.search(text) and re.search(r"degree|bachelor|master|ph\.?d|b\.?s|m\.?s|field|discipline|major", text, re.I):
        return "education"
    if CERT_RE.search(text) and not skills:
        return "certification"
    if CERT_RE.search(text) and re.search(r"\bcertifi", text, re.I):
        return "certification"
    if section == "responsibility":
        return "responsibility"
    tech = [s for s in skills if s.category not in ("soft",)]
    if tech:
        return "skill"
    if SOFT_RE.search(text):
        return "soft_skill"
    if any(re.search(rx, text, re.I) for rx in DOMAINS.values()):
        return "domain"
    return "other"


def analyse_job(text: str, *, title_override: str | None = None, company_override: str | None = None) -> JobAnalysis:
    tax = get_taxonomy()
    text = clean_text(text)
    injection = detect_injection(text)
    injected_lines = {line.strip() for line in injection}
    raw_lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if ln.strip()]

    analysis = JobAnalysis(parser_version=PARSER_VERSION, injection_warnings=injection)
    title, basis = _guess_title(lines)
    if title_override:
        title, basis = title_override, "user"
    analysis.title, analysis.title_basis = title, basis
    analysis.company = company_override or _guess_company(lines)

    for line in lines[:25]:
        m = LABELLED_FIELD_RE.match(line)
        if not m:
            continue
        key, val = m.group(1).lower(), collapse_ws(m.group(2))
        if key == "location" and not analysis.location:
            analysis.location = val
        elif key in ("employment type", "job type"):
            analysis.employment_type = val
        elif key in ("workplace type", "work arrangement", "work model"):
            for rx, arr in WORK_ARRANGEMENT:
                if rx.search(val):
                    analysis.work_arrangement = arr  # type: ignore[assignment]
                    break
    if not analysis.location:
        m = LOCATION_RE.search(" ".join(ln for ln in lines[:30] if ln.strip() not in injected_lines))
        if m:
            analysis.location = m.group(0)
    if analysis.location:
        analysis.location = re.sub(r"\s*(\(.*\)|[-–|]\s*(remote|hybrid|on-?site).*)$", "", analysis.location, flags=re.I).strip() or analysis.location
    if analysis.work_arrangement == "unknown":
        for rx, arr in WORK_ARRANGEMENT:
            if rx.search(text):
                analysis.work_arrangement = arr  # type: ignore[assignment]
                break
    if not analysis.employment_type:
        m = re.search(r"\b(full[- ]time|part[- ]time|contract(?:-to-hire)?|internship|temporary|freelance)\b", text, re.I)
        if m:
            analysis.employment_type = m.group(1).lower().replace(" ", "-")

    # ---- walk sections and lines ------------------------------------------------
    section: str | None = None
    section_heading: str | None = None
    reqs: list[Requirement] = []
    benefits_req_ids: set[int] = set()
    per_section_index: dict[str | None, int] = defaultdict(int)
    for idx, raw in enumerate(raw_lines):
        if not raw.strip():
            continue
        if raw.strip() in injected_lines:
            continue
        nxt = next((r for r in raw_lines[idx + 1: idx + 3] if r.strip()), "")
        heading = _is_heading(raw, next_is_list=strip_bullet(nxt)[1])
        if heading is not None and not strip_bullet(raw)[1]:
            sec = _section_of(heading)
            if sec is not None or len(heading.split()) <= 4:
                section, section_heading = sec, heading
                continue
        if LABELLED_FIELD_RE.match(raw) and idx < 25:
            continue
        body, is_bullet = strip_bullet(raw)
        if not body or (title and body.strip() == title):
            continue
        pieces = [body] if is_bullet or len(body) < 220 else sentence_split(body)
        for piece in pieces:
            piece = piece.strip()
            if len(piece) < 12:
                continue
            reqs.append(_make_requirement(piece, section, section_heading, idx, per_section_index, tax,
                                          mask=analysis.company))
            if section_heading and BENEFITS_HEADING.search(section_heading):
                benefits_req_ids.add(id(reqs[-1]))

    # Number and finalise.
    for n, r in enumerate(reqs, start=1):
        r.id = f"R{n}"
    title_skills = set(tax.find_canonical(analysis.title))
    for r in reqs:
        if title_skills & {s.canonical for s in r.skills}:
            r.importance = round(min(1.0, r.importance + 0.15), 3)
    analysis.requirements = reqs

    years = [r.years for r in reqs if r.kind == "experience_years" and r.category == "mandatory" and r.years]
    analysis.min_years_experience = max(years) if years else None
    if analysis.min_years_experience is None:
        years_any = [r.years for r in reqs if r.kind == "experience_years" and r.years]
        analysis.min_years_experience = min(years_any) if years_any else None
    analysis.seniority = _seniority(analysis.title, analysis.min_years_experience)  # type: ignore[assignment]
    analysis.education_requirements = [r.id for r in reqs if r.kind == "education"]
    analysis.certification_requirements = [r.id for r in reqs if r.kind == "certification"]
    for r in reqs:
        if r.kind in ("work_authorization", "clearance"):
            restriction = "other"
            low = r.text.lower()
            if r.kind == "clearance":
                restriction = "clearance"
            elif re.search(r"(not|no|unable to|cannot|won't|will not)\b.{0,40}sponsor", low) or "without sponsorship" in low or "without the need" in low:
                restriction = "no_sponsorship"
            elif re.search(r"citizen|us person|green card|permanent resident|itar", low):
                restriction = "citizenship"
            elif re.search(r"authori[sz]ed to work|work authori[sz]ation", low):
                restriction = "authorized_to_work"
            analysis.authorization.append(AuthorizationRequirement(text=r.text, restriction=restriction))  # type: ignore[arg-type]
    domain_text = "\n".join([analysis.title] + [r.text for r in reqs if id(r) not in benefits_req_ids])
    analysis.domains = sorted({d for d, rx in DOMAINS.items() if re.search(rx, domain_text, re.I)})
    analysis.skill_importance = _rank_skills(reqs, title_skills)
    return analysis


def _make_requirement(text: str, section: str | None, heading: str | None, line_no: int,
                      per_section_index: dict, tax, mask: str | None = None) -> Requirement:
    # Company names ("Harborlight Analytics") must not be read as skills.
    scan = re.sub(re.escape(mask), " " * len(mask), text) if mask else text
    hits = tax.find(scan)
    skills: list[SkillMention] = []
    for h in hits:
        if h.canonical not in {s.canonical for s in skills}:
            skills.append(SkillMention(canonical=h.canonical, as_written=h.as_written, category=tax.category(h.canonical)))
    if PREFERRED_CUE.search(text):
        category, basis = "preferred", "explicit"
    elif MANDATORY_CUE.search(text) and section != "responsibility":
        category, basis = "mandatory", "explicit"
    elif section in ("mandatory", "preferred", "responsibility", "context"):
        category, basis = section, "section"
    else:
        # Outside any recognised section: lines naming skills or experience are treated as
        # likely requirements, everything else as context. Marked as inferred.
        if skills and re.search(r"experience|proficien|knowledge|familiar|skilled|expertise|understanding", text, re.I):
            category, basis = "mandatory", "inferred"
        elif re.search(r"\byou will\b|\byou'll\b|\bresponsible for\b", text, re.I):
            category, basis = "responsibility", "inferred"
        else:
            category, basis = "context", "inferred"
    kind = _requirement_kind(text, section if basis == "section" else ("responsibility" if category == "responsibility" else None), skills)
    if kind == "work_authorization" or kind == "clearance":
        category = "mandatory" if not PREFERRED_CUE.search(text) else category
    years = None
    years_subject = None
    m = YEARS_RE.search(text)
    if m and kind == "experience_years":
        years = float(m.group(1))
        after = text[m.end(): m.end() + 80]
        sm = re.match(r"\s*(?:of\s+)?(?:professional\s+|relevant\s+|hands-on\s+|industry\s+|work\s+)?(?:experience\s+)?(?:in|with|of|as|building|using)?\s*([^.;,]+)", after, re.I)
        years_subject = sm.group(1).strip() if sm else None
    degree_level = None
    fields: list[str] = []
    if kind == "education":
        low = text.lower()
        if re.search(r"ph\.?\s?d|doctorate", low) and not re.search(r"bachelor|master|b\.?s|m\.?s", low):
            degree_level = "doctorate"
        elif re.search(r"master|m\.?s\.?\b|graduate degree", low) and not re.search(r"bachelor|b\.?s\.?\b|undergraduate", low):
            degree_level = "master"
        elif re.search(r"bachelor|b\.?s\.?\b|b\.?a\.?\b|undergraduate|degree", low):
            degree_level = "bachelor"
        fm = re.search(r"\bin\s+([A-Za-z ,/&]+?)(?:\s+or (?:a )?related|\s+or equivalent|[.;]|$)", text)
        if fm:
            fields = [f.strip() for f in re.split(r",|/|\bor\b", fm.group(1)) if f.strip()]
    base = {"mandatory": 1.0, "preferred": 0.5, "responsibility": 0.6, "context": 0.1}[category]
    pos = per_section_index[(section, category)]
    per_section_index[(section, category)] += 1
    importance = base * max(0.6, 1.0 - 0.04 * pos)
    any_of = bool(len(skills) >= 2 and ANY_OF_RE.search(text))
    return Requirement(
        id="", text=text, category=category, category_basis=basis, kind=kind, skills=skills, any_of=any_of,  # type: ignore[arg-type]
        years=years, years_subject=years_subject, degree_level=degree_level, degree_fields=fields,
        section=heading, line_no=line_no + 1, importance=round(importance, 3),
    )


def _rank_skills(reqs: list[Requirement], title_skills: set[str]) -> list[RankedSkill]:
    weight = {"mandatory": 1.0, "preferred": 0.45, "responsibility": 0.6, "context": 0.15}
    score: dict[str, float] = defaultdict(float)
    mentions: dict[str, int] = defaultdict(int)
    written: dict[str, list[str]] = defaultdict(list)
    first_seen: dict[str, int] = {}
    flags: dict[str, dict[str, bool]] = defaultdict(lambda: {"m": False, "p": False})
    tax = get_taxonomy()
    for order, r in enumerate(reqs):
        for s in r.skills:
            share = 1.0 if not r.any_of else 0.7
            score[s.canonical] += weight[r.category] * share * (0.6 + 0.4 * r.importance)
            mentions[s.canonical] += 1
            written[s.canonical].append(s.as_written)
            first_seen.setdefault(s.canonical, order)
            if r.category == "mandatory":
                flags[s.canonical]["m"] = True
            if r.category == "preferred":
                flags[s.canonical]["p"] = True
    for t in title_skills:
        score[t] += 1.0
        first_seen.setdefault(t, -1)
    if not score:
        return []
    top = max(score.values())
    ranked = []
    for canon, sc in score.items():
        forms = written.get(canon) or [canon]
        exact = [f for f in forms if f.lower() == canon.lower()]
        # Only reuse the posting's wording when it is a skill name (e.g. "scikit-learn", "Postgres"),
        # not a verb phrase that happened to match an alias ("Analyze trends").
        display_safe = [f for f in forms if " " not in f.strip() or any(c.isupper() for c in f[1:])]
        if exact:
            as_written = exact[0]
        elif display_safe:
            as_written = max(set(display_safe), key=lambda f: (display_safe.count(f), -display_safe.index(f)))
        else:
            as_written = canon
        if as_written.islower() and canon.lower() != as_written:
            as_written = canon  # keep house capitalisation for lower-case mentions like "python"
        elif as_written.lower() == canon.lower():
            as_written = canon if as_written.islower() else as_written
        ranked.append(RankedSkill(
            canonical=canon, as_written=as_written, category=tax.category(canon),
            importance=round(sc / top, 4), mentions=mentions.get(canon, 0),
            in_mandatory=flags[canon]["m"], in_preferred=flags[canon]["p"], in_title=canon in title_skills,
        ))
    ranked.sort(key=lambda r: (-r.importance, first_seen.get(r.canonical, 999), r.canonical))
    return ranked
