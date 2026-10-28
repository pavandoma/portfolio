"""Detect claims in achievement text that deserve the candidate's confirmation.

Extraction is not verification: a number on a resume is a claim until the candidate confirms
it. These checks are deterministic and conservative; they raise questions, they never
change facts.
"""

from __future__ import annotations

import re

from app.core.taxonomy import get_taxonomy
from app.schemas.common import ClaimFlag, Metric

PERCENT_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s?%")
MULTIPLIER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s?[x×](?![A-Za-z])")
MONEY_RE = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?\s?(?:[kKmMbB]|million|billion|thousand)?")
COUNT_RE = re.compile(
    r"(?<![\w.$])(\d[\d,]*(?:\.\d+)?)\+?\s+(?!%)([a-zA-Z][a-zA-Z\-]+(?:\s+[a-zA-Z][a-zA-Z\-]+)?)"
)
_COUNT_STOP = {"years", "year", "months", "month", "weeks", "days", "hours", "minutes", "am", "pm"}

COLLAB_RE = re.compile(
    r"\b(collaborat\w*|partner(?:ed|ing)? with|work(?:ed|ing) with|cross-functional\w*|"
    r"with (?:the )?(?:\w+ )?(?:stakeholders|engineers|team|teams|leadership|analysts|scientists))\b",
    re.IGNORECASE,
)
PRODUCTION_RE = re.compile(
    r"\b(production(?:-scale|-grade|-ready)?|in production|enterprise(?:-grade)?|launched|shipped|"
    r"live users|customer-facing|at scale|real users)\b",
    re.IGNORECASE,
)
DEPLOY_RE = re.compile(r"\b(deploy(?:ed|ment|ing)?|containeri[sz]ed deployment|hosted on|served on)\b", re.IGNORECASE)
LEADERSHIP_RE = re.compile(r"\b(led|lead(?:ing)?|managed|mentored|supervised|headed|directed|oversaw|owned)\b",
                           re.IGNORECASE)
ABSOLUTE_RE = re.compile(r"\b(100\s?%|zero (?:errors|downtime|defects)|always|never failed|every single|all errors)\b",
                         re.IGNORECASE)
IMPROVEMENT_RE = re.compile(r"\b(reduc\w+|improv\w+|increas\w+|cut|decreas\w+|boost\w*|accelerat\w+|sav\w+|optimi[sz]\w+|lower\w*|shorten\w*)\b",
                            re.IGNORECASE)
AWKWARD_PATTERNS = [
    (re.compile(r"\b\w+ (?:demonstrat\w+|showcas\w+) (?:understanding|end-to-end|ownership|ability)\b", re.IGNORECASE),
     "Reads as two sentences joined without punctuation (e.g. '... logic demonstrated understanding ...')."),
    (re.compile(r"\benabling directly\b|\bdirectly supporting\b", re.IGNORECASE), "Phrase is hard to parse; consider simplifying."),
    (re.compile(r"\w-foundation\b"), "Hyphenated run-on ('integrity-foundation'); split into two phrases."),
    (re.compile(r"\b(protocols|rules|checks|gates) reduced\b", re.IGNORECASE),
     "Missing connective (e.g. '... protocols that reduced ...')."),
    (re.compile(r"\bby real-time operational decision-making\b", re.IGNORECASE),
     "The stated method does not clearly explain the result."),
]

PRACTICE_CATEGORIES = {"concept", "business", "soft"}
PRACTICE_NAMES = {
    "ETL", "Data Pipelines", "Data Modeling", "Data Quality", "Dashboards", "KPI Reporting", "Feature Engineering",
    "Model Evaluation", "Time-Series Analysis", "Query Optimization", "Window Functions", "Real-Time Reporting",
    "Data Analysis", "Statistics", "A/B Testing", "Data Visualization", "Production Deployment", "Containerization",
    "Container Deployment", "Monitoring", "Reliability Engineering", "Distributed Systems", "Prompt Engineering",
    "Context Engineering", "Structured Outputs", "LLM Evaluation", "Text Classification", "Credit Risk Modeling",
    "Customer Segmentation", "Experiment Tracking", "MLOps", "Information Retrieval", "Data Engineering",
}


def extract_metrics(text: str) -> list[Metric]:
    metrics: list[Metric] = []
    seen_spans: list[tuple[int, int]] = []

    def add(m: re.Match, value: str | None, unit: str) -> None:
        s, e = m.span()
        if any(s < te and e > ts for ts, te in seen_spans):
            return
        seen_spans.append((s, e))
        ctx = text[max(0, s - 50): min(len(text), e + 40)].strip()
        try:
            num = float(value.replace(",", "")) if value else None
        except ValueError:
            num = None
        metrics.append(Metric(raw=m.group(0).strip(), value=num, unit=unit, context=ctx))

    for m in PERCENT_RE.finditer(text):
        add(m, m.group(1), "%")
    for m in MULTIPLIER_RE.finditer(text):
        add(m, m.group(1), "x")
    for m in MONEY_RE.finditer(text):
        add(m, re.sub(r"[^\d.]", "", m.group(0)) or None, "currency")
    for m in COUNT_RE.finditer(text):
        noun = m.group(2).lower().split()[0]
        if noun in _COUNT_STOP or noun in ("percent",):
            continue
        add(m, m.group(1), "count")
    metrics.sort(key=lambda x: text.find(x.raw))
    return metrics


def analyse_claims(text: str, *, parent_kind: str, parent_context: str | None = None) -> list[ClaimFlag]:
    """parent_kind: 'role' or 'project'; parent_context: project context (academic, personal...)."""
    flags: list[ClaimFlag] = []
    for metric in extract_metrics(text):
        flags.append(ClaimFlag(kind="metric", span=metric.raw,
                               message=f"Metric '{metric.raw}' is unverified. Confirm the number and how it was measured.",
                               severity="warning"))
    for m in ABSOLUTE_RE.finditer(text):
        flags.append(ClaimFlag(kind="absolute_claim", span=m.group(0),
                               message=f"Absolute claim '{m.group(0)}' invites scrutiny; confirm it is literally true.",
                               severity="warning"))
    for m in COLLAB_RE.finditer(text):
        flags.append(ClaimFlag(kind="collaboration", span=m.group(0),
                               message=f"Collaboration claim '{m.group(0)}'. Confirm who was involved before it is emphasised.",
                               severity="info"))
    academic = parent_kind == "project" and parent_context in ("academic", "personal")
    for m in PRODUCTION_RE.finditer(text):
        if academic:
            flags.append(ClaimFlag(kind="academic_vs_production", span=m.group(0),
                                   message=(f"'{m.group(0)}' appears in an {parent_context} project. Unless it served real "
                                            "users, the resume must not imply production experience."),
                                   severity="critical"))
        else:
            flags.append(ClaimFlag(kind="production", span=m.group(0),
                                   message=f"Production/scale claim '{m.group(0)}'. Confirm the system was used in production.",
                                   severity="warning"))
    for m in DEPLOY_RE.finditer(text):
        flags.append(ClaimFlag(kind="deployment", span=m.group(0),
                               message=f"Deployment claim '{m.group(0)}'. Confirm what was deployed, where, and for whom.",
                               severity="info" if not academic else "warning"))
        break
    for m in LEADERSHIP_RE.finditer(text):
        if m.group(0).lower() in ("lead", "leading") and re.search(r"lead(?:ing)? to\b", text[m.start():m.start() + 12], re.I):
            continue
        flags.append(ClaimFlag(kind="leadership", span=m.group(0),
                               message=f"Leadership/ownership claim '{m.group(0)}'. Confirm scope (people, systems, decisions).",
                               severity="info"))
        break
    if IMPROVEMENT_RE.search(text) and PERCENT_RE.search(text):
        by_count = len(re.findall(r"\bby\b", text, re.IGNORECASE)) + len(re.findall(r"\bthrough\b", text, re.IGNORECASE))
        if by_count >= 3:
            flags.append(ClaimFlag(kind="causal_clarity", span="",
                                   message="Several 'by/through' clauses: make sure the action described is what caused the result.",
                                   severity="warning"))
    for rx, msg in AWKWARD_PATTERNS:
        m = rx.search(text)
        if m:
            flags.append(ClaimFlag(kind="grammar", span=m.group(0), message=msg, severity="info"))
    return flags


def split_skills(text: str) -> tuple[list[str], list[str]]:
    """Return (technologies, competencies) mentioned in text, as canonical names."""
    tax = get_taxonomy()
    techs, comps = [], []
    for name in tax.find_canonical(text):
        node = tax.nodes.get(name)
        if node and (node.category in PRACTICE_CATEGORIES or name in PRACTICE_NAMES):
            comps.append(name)
        else:
            techs.append(name)
    return techs, comps
