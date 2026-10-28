"""Fetch a job posting from a URL safely.

Built-in fetcher: http(s) only, every hop (including redirects) must resolve to a public
address, responses are size-capped and time-limited, and only HTML / text / PDF is accepted.
When the page embeds schema.org JobPosting JSON-LD (most applicant-tracking systems do), the
title, company, location and description are taken from it.

Optional Firecrawl adapter (FIRECRAWL_API_KEY): renders JavaScript-heavy pages. Only the URL
is sent to Firecrawl; no resume data is ever included.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.core.security import UnsafeURLError, assert_public_url

USER_AGENT = "ResumeIntelligencePlatform/1.0 (+local job-description fetcher)"


class FetchError(RuntimeError):
    pass


@dataclass
class FetchedJob:
    url: str
    final_url: str
    text: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    method: str = "builtin"
    notes: list[str] = field(default_factory=list)


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article",
             "header", "footer", "table"}
    SKIP = {"script", "style", "noscript", "svg", "template", "nav", "iframe"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.json_ld: list[str] = []
        self._in_ld = False
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._in_ld = True
            return
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")
        if tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            return
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_ld:
            self.json_ld.append(data)
            return
        if self._in_title:
            self.title += data
        if not self.skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in raw.splitlines()]
        out, blank = [], 0
        for ln in lines:
            if not ln:
                blank += 1
                if blank <= 1:
                    out.append("")
                continue
            blank = 0
            out.append(ln)
        return "\n".join(out).strip()


def html_to_text(html: str) -> tuple[str, list[str], str]:
    p = _TextExtractor()
    p.feed(html)
    return p.text(), p.json_ld, p.title.strip()


def _job_posting_from_ld(blobs: list[str]) -> dict | None:
    for blob in blobs:
        try:
            data = json.loads(blob.strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                types = item.get("@type")
                types = types if isinstance(types, list) else [types]
                if "JobPosting" in types:
                    return item
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
    return None


def _from_job_posting(jp: dict) -> tuple[str, str | None, str | None, str | None]:
    desc_html = jp.get("description") or ""
    text, _ld, _t = html_to_text(html_lib.unescape(desc_html))
    org = jp.get("hiringOrganization")
    company = org.get("name") if isinstance(org, dict) else (org if isinstance(org, str) else None)
    loc = jp.get("jobLocation")
    location = None
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            parts = [addr.get("addressLocality"), addr.get("addressRegion")]
            location = ", ".join(p for p in parts if p) or None
    if jp.get("jobLocationType") == "TELECOMMUTE":
        location = (location + " (Remote)") if location else "Remote"
    return text, jp.get("title"), company, location


def _fetch_builtin(url: str, settings: Settings, transport: httpx.BaseTransport | None = None) -> FetchedJob:
    current = assert_public_url(url, allow_private=settings.fetch_allow_private)
    with httpx.Client(timeout=settings.fetch_timeout_s, follow_redirects=False, transport=transport,
                      headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf"}) as client:
        for _hop in range(4):
            with client.stream("GET", current) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("location")
                    if not loc:
                        raise FetchError("Redirect without a location.")
                    current = assert_public_url(urljoin(current, loc), allow_private=settings.fetch_allow_private)
                    continue
                if r.status_code >= 400:
                    raise FetchError(f"The page returned HTTP {r.status_code}.")
                ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype not in ("text/html", "application/xhtml+xml", "text/plain", "application/pdf", ""):
                    raise FetchError(f"Unsupported content type: {ctype}")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > settings.fetch_max_bytes:
                        raise FetchError("The page is too large.")
                break
        else:
            raise FetchError("Too many redirects.")
    if ctype == "application/pdf" or body.startswith(b"%PDF-"):
        from app.ingest.extract import extract_pdf

        return FetchedJob(url=url, final_url=current, text=extract_pdf(body).text, method="builtin-pdf")
    text_body = body.decode(r.encoding or "utf-8", errors="replace")
    if ctype == "text/plain":
        return FetchedJob(url=url, final_url=current, text=text_body.strip())
    text, ld, page_title = html_to_text(text_body)
    jp = _job_posting_from_ld(ld)
    if jp:
        desc, title, company, location = _from_job_posting(jp)
        header = "\n".join(x for x in (title, f"Company: {company}" if company else None,
                                        f"Location: {location}" if location else None) if x)
        return FetchedJob(url=url, final_url=current, text=f"{header}\n\n{desc}".strip(), title=title, company=company,
                          location=location, method="builtin-jsonld", notes=["Read schema.org JobPosting data"])
    notes = []
    if len(text) < 400:
        notes.append("Very little text found; the page may need JavaScript. Paste the description or configure Firecrawl.")
    return FetchedJob(url=url, final_url=current, text=text, title=page_title or None, notes=notes)


def _fetch_firecrawl(url: str, settings: Settings, transport: httpx.BaseTransport | None = None) -> FetchedJob:
    assert settings.firecrawl_api_key is not None
    with httpx.Client(base_url=settings.firecrawl_base_url, timeout=60.0, transport=transport,
                      headers={"Authorization": f"Bearer {settings.firecrawl_api_key.get_secret_value()}"}) as client:
        r = client.post("/v2/scrape", json={"url": url, "formats": ["markdown"], "onlyMainContent": True})
    if r.status_code >= 400:
        raise FetchError(f"Firecrawl returned HTTP {r.status_code}.")
    data = r.json().get("data") or {}
    md = data.get("markdown") or ""
    meta = data.get("metadata") or {}
    if not md.strip():
        raise FetchError("Firecrawl returned no content.")
    return FetchedJob(url=url, final_url=meta.get("sourceURL") or url, text=md, title=meta.get("title"),
                      method="firecrawl")


def fetch_job(url: str, settings: Settings, *, prefer: str = "auto",
              transport: httpx.BaseTransport | None = None) -> FetchedJob:
    """prefer: auto | builtin | firecrawl. Auto uses the built-in fetcher and falls back to Firecrawl
    (when configured) for pages that need JavaScript."""
    assert_public_url(url, allow_private=settings.fetch_allow_private)
    if prefer == "firecrawl":
        if not settings.firecrawl_api_key:
            raise FetchError("FIRECRAWL_API_KEY is not set.")
        return _fetch_firecrawl(url, settings, transport)
    try:
        job = _fetch_builtin(url, settings, transport)
    except (FetchError, httpx.HTTPError, UnsafeURLError) as exc:
        if isinstance(exc, UnsafeURLError) or prefer == "builtin" or not settings.firecrawl_api_key:
            raise FetchError(str(exc)) from exc
        return _fetch_firecrawl(url, settings, transport)
    if prefer == "auto" and settings.firecrawl_api_key and len(job.text) < 400:
        try:
            return _fetch_firecrawl(url, settings, transport)
        except FetchError:
            pass
    return job
