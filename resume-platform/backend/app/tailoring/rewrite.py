"""Rule-based wording cleanup and the fact-preservation check every rewrite must pass.

Wording may change; facts may not. ``fact_check`` compares a rewrite against its source
evidence and rejects new numbers, new technologies, new named entities, and new
production / leadership / collaboration claims.
"""

from __future__ import annotations

import re

from app.core.taxonomy import get_taxonomy
from app.core.text import collapse_ws
from app.ingest.claims import COLLAB_RE, LEADERSHIP_RE, PRODUCTION_RE
from app.schemas.common import FactCheck
from app.tailoring.style import (
    SELF_ASSESSMENT_RE,
    TRAILING_PARTICIPLE_RE,
    WEAK_OPENERS,
    gerund_to_past,
    plain_substitutions,
)

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_ACADEMIC_PRODUCTION_ADJ = re.compile(
    r"\b(?:production-scale|production-grade|production-ready|enterprise-grade|enterprise-scale)\s+", re.IGNORECASE
)
YEARS_RE = re.compile(r"\b\d+\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)
CAPWORD_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)")


def _ensure_period(text: str) -> str:
    text = text.rstrip(" ,;:")
    return text if text.endswith((".", "!", "?")) else text + "."


def rule_cleanup(text: str, *, academic: bool = False) -> str:
    """Conservative cleanup: never adds information, only removes filler or simplifies words."""
    out = plain_substitutions(text)
    out = SELF_ASSESSMENT_RE.sub("", out)
    out = TRAILING_PARTICIPLE_RE.sub(".", out) if re.search(
        r",\s*(demonstrating|showcasing|highlighting|underscoring|reflecting)\b", out, re.IGNORECASE) else out
    m = WEAK_OPENERS.match(out)
    if m:
        rest = out[m.end():].lstrip()
        first = rest.split(" ", 1)
        past = gerund_to_past(first[0]) if first else None
        if past:
            out = past.capitalize() + (" " + first[1] if len(first) > 1 else "")
    if academic:
        out = _ACADEMIC_PRODUCTION_ADJ.sub("", out)
        out = re.sub(r"^Launched\b", "Built", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r",\s*,", ",", out)
    out = collapse_ws(out)
    if out:
        out = out[0].upper() + out[1:]
    out = _ensure_period(out)
    # Safety: a cleanup may only remove filler. If it drops numbers, technologies or a large
    # share of the words, keep the original text instead.
    tax = get_taxonomy()
    lost_numbers = _norm_numbers(text) - _norm_numbers(out)
    lost_tech = set(tax.find_canonical(text)) - set(tax.find_canonical(out)) - {"Production Deployment"}
    if lost_numbers or (lost_tech and not academic) or len(out.split()) < 0.6 * len(text.split()):
        return _ensure_period(collapse_ws(plain_substitutions(text)))
    return out


def _norm_numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER_RE.findall(text)}


def _expanded_skills(texts: list[str]) -> set[str]:
    tax = get_taxonomy()
    found: set[str] = set()
    for t in texts:
        for name in tax.find_canonical(t):
            found.add(name)
            found.update(tax.ancestors(name))
    return found


def fact_check(new_text: str, sources: list[str], *, academic: bool = False,
               allowed_extra_terms: list[str] | None = None) -> FactCheck:
    """Check that ``new_text`` makes no claim absent from ``sources``."""
    problems: list[str] = []
    joined = " ".join(sources)
    joined_lower = joined.lower()

    new_numbers = sorted(_norm_numbers(new_text) - _norm_numbers(joined))
    if new_numbers:
        problems.append(f"Introduces numbers not present in the source: {', '.join(new_numbers)}")

    tax = get_taxonomy()
    allowed = _expanded_skills(sources + (allowed_extra_terms or []))
    new_tech = [n for n in tax.find_canonical(new_text) if n not in allowed]
    if new_tech:
        problems.append(f"Mentions skills/technologies not supported by the source: {', '.join(new_tech)}")

    new_risky: list[str] = []
    for rx, label in ((PRODUCTION_RE, "production/scale"), (LEADERSHIP_RE, "leadership"), (COLLAB_RE, "collaboration")):
        for m in rx.finditer(new_text):
            term = m.group(0).lower()
            if label == "leadership" and term in ("lead", "leading"):
                continue
            if not rx.search(joined):
                new_risky.append(f"{label}: '{m.group(0)}'")
            elif academic and label == "production/scale":
                new_risky.append(f"{label}: '{m.group(0)}' in an academic project")
    if new_risky:
        problems.append("Adds or keeps claims that need evidence: " + "; ".join(sorted(set(new_risky))))

    if YEARS_RE.search(new_text) and not YEARS_RE.search(joined):
        problems.append("Adds a years-of-experience claim not present in the source.")

    for m in CAPWORD_RE.finditer(new_text):
        phrase = m.group(1)
        if phrase.lower() in joined_lower or tax.canonical(phrase):
            continue
        if any(w.lower() in joined_lower for w in phrase.split()):
            continue
        problems.append(f"Introduces a name not present in the source: '{phrase}'")
        break

    return FactCheck(
        passed=not problems,
        problems=problems,
        new_numbers=new_numbers,
        new_technologies=new_tech,
        new_risky_terms=new_risky,
    )
