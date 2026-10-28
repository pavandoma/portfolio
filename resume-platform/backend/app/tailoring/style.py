"""Human-voice style rules.

Recruiters increasingly skim past text that reads as machine-written. These rules catch the
usual tells (inflated vocabulary, trailing "-ing" clauses, empty adjectives, em-dash chains,
repeated openers, keyword stuffing) and power both the rule-based cleanup and the QA report.
"""

from __future__ import annotations

import re
from collections import Counter

# phrase -> plain replacement ("" means delete). Only substitutions that never change a fact.
PLAIN_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bleveraging\b", "using"),
    (r"\bleveraged\b", "used"),
    (r"\bleverages\b", "uses"),
    (r"\bleverage\b", "use"),
    (r"\butilizing\b", "using"),
    (r"\butilized\b", "used"),
    (r"\butilizes\b", "uses"),
    (r"\butilize\b", "use"),
    (r"\butilization of\b", "use of"),
    (r"\bin order to\b", "to"),
    (r"\bsuccessfully\s+", ""),
    (r"\beffectively\s+", ""),
    (r"\bseamlessly\s+", ""),
    (r"\bvarious\s+", ""),
]

AI_TELLS: dict[str, str] = {
    "spearhead": "Plain verbs like 'led' or 'started' read as more credible.",
    "cutting-edge": "Name the technology instead.",
    "state-of-the-art": "Name the technique or result instead.",
    "seamless": "Usually empty; say what actually happened.",
    "robust": "Say what made it reliable (tests, retries, monitoring).",
    "synergy": "Corporate filler.",
    "passionate": "Show it with results instead.",
    "results-driven": "Filler; the bullets should show results.",
    "detail-oriented": "Filler; show it.",
    "proven track record": "Filler; show the record.",
    "fostering": "Common AI-writing tell.",
    "delve": "Common AI-writing tell.",
    "showcasing": "Common AI-writing tell.",
    "pivotal": "Inflated; say what changed.",
    "innovative": "Let the work speak for itself.",
    "game-changer": "Inflated.",
    "best-in-class": "Inflated.",
    "world-class": "Inflated.",
    "holistic": "Vague.",
    "empower": "Vague.",
    "unlock": "Vague marketing verb.",
    "harness": "Vague marketing verb.",
    "elevate": "Vague marketing verb.",
    "end-to-end ownership": "Self-assessment; describe what you owned.",
    "demonstrating": "Trailing 'demonstrating ...' clauses read as filler.",
    "demonstrated understanding": "Self-assessment; drop it or show the result.",
    "dynamic": "Filler adjective.",
    "meticulous": "Filler adjective.",
    "transformative": "Inflated.",
    "a testament to": "Common AI-writing tell.",
    "fast-paced": "Cliche.",
    "team player": "Cliche; show collaboration in a bullet.",
    "hardworking": "Cliche.",
    "self-starter": "Cliche.",
    "go-getter": "Cliche.",
    "thrive": "Cliche.",
    "tapestry": "Common AI-writing tell.",
    "landscape": "Usually filler ('the AI landscape').",
    "realm": "Common AI-writing tell.",
    "navigate the complexities": "Common AI-writing tell.",
    "significantly": "Use the number instead.",
    "drastically": "Use the number instead.",
    "leverage": "Use 'use'.",
    "utilize": "Use 'use'.",
}
_AI_TELL_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(AI_TELLS, key=len, reverse=True)) + r")\w*",
                         re.IGNORECASE)
TRAILING_PARTICIPLE_RE = re.compile(
    r",\s*(?:thereby\s+)?(ensuring|enabling|demonstrating|showcasing|highlighting|fostering|empowering|driving|"
    r"underscoring|reflecting)\b[^.;]*\.?$",
    re.IGNORECASE,
)
# Only a trailing ", demonstrating X" clause is removed; mid-sentence phrases are left for a human rewrite.
SELF_ASSESSMENT_RE = re.compile(
    r",\s*(?:demonstrat|showcas|highlight)\w* (?:strong )?(?:end-to-end )?(?:ownership|understanding|ability|expertise|proficiency)"
    r"(?: of| in)? [^.;]*(?=\.?\s*$)",
    re.IGNORECASE,
)
WEAK_OPENERS = re.compile(
    r"^(responsible for|worked on|helped(?: to)?|assisted (?:with|in)|involved in|participated in|tasked with|"
    r"duties included)\b",
    re.IGNORECASE,
)

IRREGULAR_PAST = {
    "build": "built", "lead": "led", "write": "wrote", "run": "ran", "make": "made", "teach": "taught",
    "drive": "drove", "set": "set", "put": "put", "take": "took", "give": "gave", "find": "found",
    "keep": "kept", "begin": "began", "choose": "chose", "hold": "held", "meet": "met", "send": "sent",
    "spend": "spent", "win": "won", "draw": "drew", "grow": "grew", "do": "did", "get": "got",
}
STRONG_VERBS = {
    "built", "designed", "developed", "implemented", "created", "engineered", "automated", "analyzed", "reduced",
    "improved", "increased", "optimized", "standardized", "documented", "validated", "trained", "evaluated",
    "deployed", "migrated", "modeled", "wrote", "led", "launched", "delivered", "integrated", "refactored", "tested",
    "compared", "cut", "maintained", "monitored", "partnered", "collaborated", "prototyped", "researched",
    "fine-tuned", "containerized", "configured", "established", "defined", "investigated", "identified", "streamlined",
    "presented", "reported", "visualized", "cleaned", "scaled", "shipped", "ran", "added", "replaced", "extended",
    "measured", "tuned", "set", "mapped", "consolidated", "audited", "forecasted", "segmented", "classified",
}

_DASH_CHAIN_RE = re.compile(r"—|--")


def plain_substitutions(text: str) -> str:
    out = text
    for pattern, repl in PLAIN_REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    out = re.sub(r"(?<=\w) & (?=\w)", " and ", out)
    return out


def ai_tells(text: str) -> list[tuple[str, str]]:
    hits = []
    for m in _AI_TELL_RE.finditer(text):
        key = next((k for k in AI_TELLS if m.group(0).lower().startswith(k.lower())), m.group(1).lower())
        hits.append((m.group(0), AI_TELLS.get(key, "")))
    if TRAILING_PARTICIPLE_RE.search(text):
        hits.append(("trailing '-ing' clause", "Ending a bullet with ', ensuring/enabling ...' is a common AI tell."))
    if len(_DASH_CHAIN_RE.findall(text)) >= 2:
        hits.append(("em dashes", "Several em dashes in one line read as generated text."))
    return hits


def to_past_tense(verb: str) -> str:
    v = verb.lower()
    if v in IRREGULAR_PAST:
        return IRREGULAR_PAST[v]
    if v.endswith("e"):
        return v + "d"
    if v.endswith("y") and len(v) > 2 and v[-2] not in "aeiou":
        return v[:-1] + "ied"
    return v + "ed"


GERUND_PAST = {
    "designing": "designed", "building": "built", "developing": "developed", "maintaining": "maintained",
    "creating": "created", "managing": "managed", "analyzing": "analyzed", "analysing": "analysed",
    "writing": "wrote", "running": "ran", "supporting": "supported", "coordinating": "coordinated",
    "preparing": "prepared", "tracking": "tracked", "monitoring": "monitored", "testing": "tested",
    "reporting": "reported", "documenting": "documented", "implementing": "implemented",
    "optimizing": "optimized", "automating": "automated", "leading": "led", "training": "trained",
    "cleaning": "cleaned", "handling": "handled", "reviewing": "reviewed", "updating": "updated",
    "organizing": "organized", "conducting": "conducted", "collecting": "collected", "processing": "processed",
    "deploying": "deployed", "migrating": "migrated", "modeling": "modeled", "troubleshooting": "troubleshot",
    "resolving": "resolved", "communicating": "communicated", "providing": "provided", "producing": "produced",
    "using": "used", "making": "made", "evaluating": "evaluated", "integrating": "integrated",
    "researching": "researched", "presenting": "presented", "visualizing": "visualized", "planning": "planned",
}


def gerund_to_past(word: str) -> str | None:
    return GERUND_PAST.get(word.lower())


def first_word(text: str) -> str:
    m = re.match(r"\W*([A-Za-z\-]+)", text)
    return m.group(1).lower() if m else ""


def keyword_repetition(texts: list[str], keywords: list[str], limit: int = 3) -> dict[str, int]:
    """Count how often each keyword appears across the resume; return those above the limit."""
    joined = "\n".join(texts).lower()
    counts = {}
    for kw in keywords:
        n = len(re.findall(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", joined))
        if n > limit:
            counts[kw] = n
    return counts


def repeated_openers(bullets: list[str]) -> list[str]:
    counts = Counter(first_word(b) for b in bullets if b)
    return [w for w, c in counts.items() if c >= 3 and w]
