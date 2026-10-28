"""Parsing and formatting of resume-style dates ("Sep 2024", "Jan 2026 - Present", "05/2024")."""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
    "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

_MONTH_RX = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_TOKEN = rf"(?:{_MONTH_RX}\.?\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}}-\d{{2}}|(?:19|20)\d{{2}})"
PRESENT = r"(?:present|current|now|ongoing|today)"
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to|until)\s*(?P<end>{DATE_TOKEN}|{PRESENT})", re.IGNORECASE
)
SINGLE_DATE_RE = re.compile(rf"(?:(?:expected|anticipated|graduat\w*)\s*:?\s*)?(?P<d>{DATE_TOKEN})", re.IGNORECASE)


def parse_date(token: str) -> str | None:
    """Return YYYY-MM (month defaults to 01 for bare years), 'present', or None."""
    t = token.strip().lower().rstrip(".")
    if re.fullmatch(PRESENT, t):
        return "present"
    m = re.fullmatch(rf"({_MONTH_RX})\.?\s+(\d{{4}})", t)
    if m:
        key = m.group(1)[:4] if m.group(1).startswith("sept") else m.group(1)[:3]
        month = MONTHS.get(key, MONTHS.get(m.group(1)))
        return f"{int(m.group(2)):04d}-{month:02d}" if month else None
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"(\d{4})-(\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.fullmatch(r"((?:19|20)\d{2})", t)
    if m:
        return f"{m.group(1)}-01"
    return None


def find_date_range(text: str) -> tuple[str | None, str | None, str] | None:
    """Find a date range; returns (start, end, matched_text)."""
    m = DATE_RANGE_RE.search(text)
    if m:
        return parse_date(m.group("start")), parse_date(m.group("end")), m.group(0)
    return None


def find_single_date(text: str) -> tuple[str | None, str] | None:
    m = SINGLE_DATE_RE.search(text)
    if m:
        return parse_date(m.group("d")), m.group(0)
    return None


def format_month(value: str | None) -> str:
    if not value:
        return ""
    if value == "present":
        return "Present"
    y, m = value.split("-")
    return f"{MONTH_ABBR[int(m)]} {y}"


def format_range(start: str | None, end: str | None) -> str:
    if start and end:
        return f"{format_month(start)} - {format_month(end)}"
    return format_month(end or start)


def months_between(start: str | None, end: str | None, today: date | None = None) -> int:
    if not start:
        return 0
    today = today or date.today()
    sy, sm = (int(x) for x in start.split("-"))
    if not end or end == "present":
        ey, em = today.year, today.month
    else:
        ey, em = (int(x) for x in end.split("-"))
    return max(0, (ey - sy) * 12 + (em - sm) + 1)


def is_past(value: str | None, today: date | None = None) -> bool:
    if not value or value == "present":
        return False
    today = today or date.today()
    y, m = (int(x) for x in value.split("-"))
    return (y, m) <= (today.year, today.month)
