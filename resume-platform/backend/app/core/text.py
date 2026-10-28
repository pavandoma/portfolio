"""Text normalisation, tokenisation and a small deterministic similarity model.

The similarity model is a TF-IDF cosine over lightly stemmed tokens. It is used as an
additional signal next to the explicit skill matching; it is deterministic, needs no
network and no model download, so identical inputs always give identical scores.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable

_LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_PUNCT_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
    "−": "-", " ": " ", "​": "", "‌": "", "‍": "", "﻿": "",
}
BULLET_CHARS = "•●▪■◦‣⁃∙·➢➔►▸*–-"

STOPWORDS = frozenset(
    """a an and are as at be been being by for from has have in into is it its of on or that the
    their them they this to was were will with within across via using use used our your you we
    i me my he she his her who whom which what when where why how all any both each few more most
    other some such no nor not only own same so than too very can just should now also etc per
    including include includes ability strong experience experienced work working years year""".split()
)


def clean_text(text: str) -> str:
    """Normalise unicode, ligatures, smart punctuation and invisible characters."""
    text = unicodedata.normalize("NFKC", text)
    for k, v in {**_LIGATURES, **_PUNCT_MAP}.items():
        text = text.replace(k, v)
    # Drop control characters except newline/tab.
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return text


def collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_bullet(line: str) -> tuple[str, bool]:
    stripped = line.lstrip()
    if stripped and stripped[0] in BULLET_CHARS and (len(stripped) == 1 or stripped[1] in " \t​"):
        return stripped[1:].strip(), True
    m = re.match(r"^(\d{1,2}[.)]|[a-z][.)])\s+", stripped)
    if m:
        return stripped[m.end():].strip(), True
    return stripped.strip(), False


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalize_key(text: str) -> str:
    """Lowercase alphanumeric key for comparisons (company names, titles)."""
    text = clean_text(text).lower()
    text = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|gmbh|plc)\b\.?", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*[a-z0-9+#]|[a-z0-9]")


def stem(token: str) -> str:
    """A tiny suffix stripper. Good enough to align 'pipelines'/'pipeline', 'optimized'/'optimizing'."""
    for suffix, repl in (
        ("ization", "ize"), ("isation", "ize"), ("ational", "ate"), ("ations", "ate"), ("ation", "ate"),
        ("ments", ""), ("ment", ""), ("ness", ""), ("ingly", ""), ("edly", ""), ("ies", "y"),
        ("ing", ""), ("ers", ""), ("er", ""), ("ed", ""), ("es", ""), ("s", ""),
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: len(token) - len(suffix)] + repl
    return token


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    tokens = _TOKEN_RE.findall(clean_text(text).lower())
    out = []
    for t in tokens:
        t = t.strip("./-")
        if not t or (not keep_stopwords and t in STOPWORDS):
            continue
        out.append(stem(t))
    return out


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'+#./%-]*", text)


def word_count(text: str) -> int:
    return len(words(text))


class TfidfIndex:
    """Deterministic TF-IDF cosine similarity over a fixed document collection."""

    def __init__(self, documents: Iterable[str]):
        self.docs = [Counter(tokenize(d)) for d in documents]
        n = len(self.docs)
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        self.vectors = [self._vec(d) for d in self.docs]

    def _vec(self, counts: Counter[str]) -> dict[str, float]:
        v = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def query(self, text: str) -> list[float]:
        q = self._vec(Counter(tokenize(text)))
        return [round(sum(w * vec.get(t, 0.0) for t, w in q.items()), 6) for vec in self.vectors]


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def sentence_split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [p.strip() for p in parts if p.strip()]
