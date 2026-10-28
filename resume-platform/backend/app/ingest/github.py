"""GitHub repository evidence: README, languages and topics of a public (or token-accessible) repo.

Repository content supports technology claims ("this project used FastAPI") but does not prove
metrics or outcomes; those stay unverified until the candidate confirms them.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

import httpx

from app.config import Settings
from app.core.taxonomy import get_taxonomy
from app.core.text import jaccard, tokenize

REPO_RE = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


class GitHubError(RuntimeError):
    pass


@dataclass
class RepoEvidence:
    owner: str
    repo: str
    url: str
    description: str
    languages: list[str]
    topics: list[str]
    readme_excerpt: str
    technologies: list[str] = field(default_factory=list)
    stars: int = 0
    pushed_at: str | None = None


def parse_repo_url(url: str) -> tuple[str, str]:
    m = REPO_RE.match(url.strip())
    if not m:
        raise GitHubError("Not a GitHub repository URL (expected https://github.com/<owner>/<repo>).")
    return m.group(1), m.group(2)


def fetch_repo(url: str, settings: Settings, transport: httpx.BaseTransport | None = None) -> RepoEvidence:
    owner, repo = parse_repo_url(url)
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ResumeIntelligencePlatform/1.0",
               "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=20.0, transport=transport) as gh:
        r = gh.get(f"/repos/{owner}/{repo}")
        if r.status_code == 404:
            raise GitHubError("Repository not found (or private without a token).")
        if r.status_code >= 400:
            raise GitHubError(f"GitHub API error {r.status_code}.")
        meta = r.json()
        langs = gh.get(f"/repos/{owner}/{repo}/languages")
        languages = sorted(langs.json(), key=lambda k: -langs.json()[k]) if langs.status_code == 200 else []
        readme = ""
        rr = gh.get(f"/repos/{owner}/{repo}/readme")
        if rr.status_code == 200 and rr.json().get("encoding") == "base64":
            readme = base64.b64decode(rr.json().get("content", "")).decode("utf-8", errors="replace")
    topics = meta.get("topics") or []
    text = " ".join([meta.get("description") or "", readme, " ".join(topics), " ".join(languages)])
    techs = get_taxonomy().find_canonical(text)
    return RepoEvidence(owner=owner, repo=repo, url=meta.get("html_url") or f"https://github.com/{owner}/{repo}",
                        description=meta.get("description") or "", languages=languages, topics=topics,
                        readme_excerpt=readme[:4000], technologies=techs, stars=meta.get("stargazers_count", 0),
                        pushed_at=meta.get("pushed_at"))


def best_project_match(evidence: RepoEvidence, projects) -> tuple[object | None, float]:
    """Find the profile project this repository most likely belongs to (by name and technologies)."""
    best, best_score = None, 0.0
    repo_tokens = tokenize(evidence.repo.replace("-", " ").replace("_", " ") + " " + evidence.description)
    for p in projects:
        name_score = jaccard(repo_tokens, tokenize(p.name + " " + (p.subtitle or "")))
        tech_score = jaccard(evidence.technologies, p.technologies)
        score = 0.6 * name_score + 0.4 * tech_score
        if score > best_score:
            best, best_score = p, score
    return (best, round(best_score, 3)) if best_score >= 0.15 else (None, round(best_score, 3))
