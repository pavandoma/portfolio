"""Job intake (text, file or URL), analysis, duplicate detection and match persistence."""

from __future__ import annotations

import hashlib
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.jobs.jd_parser import analyse_job
from app.matching.engine import requirement_key, score_profile
from app.models import Job, MatchRecord
from app.schemas.job import JobAnalysis
from app.schemas.match import MatchReport, Weights
from app.services import profiles
from app.services.profiles import NotFound, audit

TRACKING_PARAMS = {"gh_src", "src", "source", "ref", "referrer", "trk", "trackingid", "refid", "lever-source",
                   "lever-origin", "utm", "gclid", "fbclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi", "sid"}


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return None
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False)
             if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).lower().encode("utf-8")).hexdigest()


def find_duplicate(session: Session, *, canon: str | None, dedupe_key: str, thash: str,
                   has_identity: bool) -> Job | None:
    conds = [Job.text_sha256 == thash]
    if canon:
        conds.append(Job.canonical_url == canon)
    if has_identity:
        conds.append(Job.dedupe_key == dedupe_key)
    return session.scalars(select(Job).where(or_(*conds)).where(Job.duplicate_of.is_(None))
                           .order_by(Job.created_at)).first()


def create_job(session: Session, text: str, *, url: str | None = None, title: str | None = None,
               company: str | None = None, source_document_id: str | None = None,
               allow_duplicate: bool = False) -> tuple[Job, bool]:
    """Returns (job, is_duplicate). Duplicates return the existing record unless allow_duplicate."""
    analysis = analyse_job(text, title_override=title, company_override=company)
    canon = canonical_url(url)
    key = requirement_key(analysis.company, analysis.title, analysis.location)
    thash = text_hash(text)
    dup = find_duplicate(session, canon=canon, dedupe_key=key, thash=thash,
                         has_identity=bool(analysis.company and analysis.title))
    if dup and not allow_duplicate:
        audit(session, "job", dup.id, "duplicate_detected", {"url": url})
        return dup, True
    job = Job(title=analysis.title, company=analysis.company, location=analysis.location, url=url,
              canonical_url=canon, dedupe_key=key, text_sha256=thash, raw_text=text,
              analysis=analysis.model_dump(mode="json"), source_document_id=source_document_id,
              duplicate_of=dup.id if dup else None)
    session.add(job)
    session.flush()
    audit(session, "job", job.id, "created", {"title": job.title, "company": job.company, "url": url})
    return job, False


def get_job(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise NotFound("Job not found")
    return job


def job_analysis(job: Job) -> JobAnalysis:
    return JobAnalysis.model_validate(job.analysis)


def update_job_fields(session: Session, job_id: str, *, title: str | None = None, company: str | None = None,
                      location: str | None = None) -> Job:
    job = get_job(session, job_id)
    analysis = job_analysis(job)
    if title:
        analysis = analyse_job(job.raw_text, title_override=title, company_override=company or analysis.company)
    if company:
        analysis.company = company
    if location:
        analysis.location = location
    job.title, job.company, job.location = analysis.title, analysis.company, analysis.location
    job.analysis = analysis.model_dump(mode="json")
    job.dedupe_key = requirement_key(job.company, job.title, job.location)
    audit(session, "job", job.id, "edited", {"title": title, "company": company, "location": location})
    return job


def run_match(session: Session, job_id: str, weights: Weights | None = None,
              today: date | None = None) -> tuple[MatchRecord, MatchReport]:
    job = get_job(session, job_id)
    _profile, rev, data = profiles.current(session)
    report = score_profile(data, job_analysis(job), weights, today=today)
    existing = session.scalars(select(MatchRecord).where(MatchRecord.job_id == job_id,
                                                        MatchRecord.input_hash == report.input_hash)).first()
    if existing:
        return existing, report
    rec = MatchRecord(job_id=job_id, profile_revision_id=rev.id, input_hash=report.input_hash,
                      job_fit=report.job_fit.total, report=report.model_dump(mode="json"))
    session.add(rec)
    session.flush()
    return rec, report


def latest_match(session: Session, job_id: str) -> MatchRecord | None:
    return session.scalars(select(MatchRecord).where(MatchRecord.job_id == job_id)
                           .order_by(MatchRecord.created_at.desc())).first()
