"""Skill taxonomy: canonical names, synonyms, hierarchy and "related but not equal" links."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.text import clean_text

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "skills.yaml"

Relation = str  # "exact" | "specific_satisfies_generic" | "sibling" | "generic_only" | "related" | "none"


@dataclass
class SkillNode:
    name: str
    category: str
    aliases: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    family: bool = False
    related: list[str] = field(default_factory=list)
    case_sensitive: bool = False


@dataclass(frozen=True)
class SkillHit:
    canonical: str
    as_written: str
    start: int
    end: int


@dataclass(frozen=True)
class Relationship:
    relation: Relation
    via: str | None = None


class Taxonomy:
    def __init__(self, path: Path = TAXONOMY_PATH):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.category_labels: dict[str, str] = raw.get("categories", {})
        self.nodes: dict[str, SkillNode] = {}
        for item in raw["skills"]:
            node = SkillNode(
                name=item["name"],
                category=item.get("cat", "concept"),
                aliases=list(item.get("aliases", [])),
                parents=list(item.get("parents", [])),
                family=bool(item.get("family", False)),
                related=list(item.get("related", [])),
                case_sensitive=bool(item.get("cs", False)),
            )
            self.nodes[node.name] = node
        self._lower_index: dict[str, str] = {}
        patterns: list[tuple[str, str, bool]] = []
        for node in self.nodes.values():
            for form in [node.name, *node.aliases]:
                cs = node.case_sensitive or (len(form) <= 4 and any(c.isupper() for c in form))
                patterns.append((form, node.name, cs))
                self._lower_index.setdefault(form.lower(), node.name)
        # Longest forms first so "AWS ECS" wins over "ECS", "PostgreSQL" over "SQL".
        patterns.sort(key=lambda p: (-len(p[0]), p[0]))
        self._patterns = [(re.compile(self._form_regex(f), 0 if cs else re.IGNORECASE), canon) for f, canon, cs in patterns]
        self._ancestors_cache: dict[str, frozenset[str]] = {}

    @staticmethod
    def _form_regex(form: str) -> str:
        parts = []
        for ch in form:
            if ch == " ":
                parts.append(r"[\s\-]+")
            elif ch == "-":
                parts.append(r"[\s\-]?")
            else:
                parts.append(re.escape(ch))
        return rf"(?<![A-Za-z0-9+#&]){''.join(parts)}(?![A-Za-z0-9+#&])"

    # -- lookup -----------------------------------------------------------------
    def canonical(self, text: str) -> str | None:
        key = clean_text(text).strip().lower()
        if key in self._lower_index:
            return self._lower_index[key]
        hits = self.find(text)
        if len(hits) == 1 and (hits[0].end - hits[0].start) >= len(text.strip()) * 0.6:
            return hits[0].canonical
        return None

    def category(self, canonical: str) -> str | None:
        node = self.nodes.get(canonical)
        return node.category if node else None

    def category_label(self, canonical: str) -> str | None:
        cat = self.category(canonical)
        return self.category_labels.get(cat) if cat else None

    def find(self, text: str) -> list[SkillHit]:
        """Find skill mentions; overlapping matches resolve to the longest form."""
        text = clean_text(text)
        taken: list[tuple[int, int]] = []
        hits: list[SkillHit] = []
        for rx, canon in self._patterns:
            for m in rx.finditer(text):
                s, e = m.span()
                if any(s < te and e > ts for ts, te in taken):
                    continue
                taken.append((s, e))
                hits.append(SkillHit(canon, m.group(0), s, e))
        hits.sort(key=lambda h: h.start)
        return hits

    def find_canonical(self, text: str) -> list[str]:
        seen: list[str] = []
        for h in self.find(text):
            if h.canonical not in seen:
                seen.append(h.canonical)
        return seen

    # -- hierarchy -------------------------------------------------------------
    def ancestors(self, name: str) -> frozenset[str]:
        if name in self._ancestors_cache:
            return self._ancestors_cache[name]
        out: set[str] = set()
        stack = list(self.nodes[name].parents) if name in self.nodes else []
        while stack:
            p = stack.pop()
            if p in out:
                continue
            out.add(p)
            if p in self.nodes:
                stack.extend(self.nodes[p].parents)
        result = frozenset(out)
        self._ancestors_cache[name] = result
        return result

    # Direct parents that make their children "related but not interchangeable".
    SIBLING_PARENTS = frozenset({"AWS", "Azure", "GCP"})

    def families(self, name: str) -> set[str]:
        node = self.nodes.get(name)
        if not node:
            return set()
        return {p for p in node.parents if p in self.SIBLING_PARENTS or (p in self.nodes and self.nodes[p].family)}

    def relationship(self, candidate: str, required: str) -> Relationship:
        """How a candidate skill relates to a required skill.

        exact                       same canonical skill
        specific_satisfies_generic  candidate is a specific instance of the requirement
                                    (PyTorch for "deep learning frameworks")
        sibling                     both belong to the same narrow family; related, not equal
                                    (TensorFlow for "PyTorch", ECS for "Kubernetes")
        generic_only                candidate only has the broader concept ("deep learning"
                                    for "PyTorch")
        related                     explicitly marked as related
        none                        no relationship
        """
        if candidate == required:
            return Relationship("exact")
        if required in self.ancestors(candidate):
            return Relationship("specific_satisfies_generic", via=required)
        shared = self.families(candidate) & self.families(required)
        if shared:
            return Relationship("sibling", via=sorted(shared)[0])
        r_node = self.nodes.get(required)
        if r_node and candidate in r_node.parents:
            return Relationship("generic_only", via=candidate)
        c_node = self.nodes.get(candidate)
        if (c_node and required in c_node.related) or (r_node and candidate in r_node.related):
            return Relationship("related")
        return Relationship("none")


@lru_cache
def get_taxonomy() -> Taxonomy:
    return Taxonomy()
