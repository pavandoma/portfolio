"""ORM tables. Structured documents (profile revisions, analyses, resumes) are stored as JSON
validated by the Pydantic schemas; relational columns hold what we filter and join on."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.schemas.common import utcnow


def new_id() -> str:
    return uuid.uuid4().hex


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20))  # resume | supporting | job | repository
    file_type: Mapped[str] = mapped_column(String(10))  # pdf | docx | txt | url | github
    display_name: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), default="")
    current_revision_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    revisions: Mapped[list[ProfileRevision]] = relationship(back_populates="profile", cascade="all, delete-orphan",
                                                             order_by="ProfileRevision.revision_no")


class ProfileRevision(Base):
    """Immutable snapshot of the master profile. Edits create new revisions."""

    __tablename__ = "profile_revisions"
    __table_args__ = (UniqueConstraint("profile_id", "revision_no"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    parent_revision_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    profile: Mapped[Profile] = relationship(back_populates="revisions")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(60))
    actor: Mapped[str] = mapped_column(String(40), default="user")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), default="")
    company: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(600), index=True)
    text_sha256: Mapped[str] = mapped_column(String(64), index=True)
    raw_text: Mapped[str] = mapped_column(Text)
    analysis: Mapped[dict] = mapped_column(JSON)
    source_document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MatchRecord(Base):
    __tablename__ = "match_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    profile_revision_id: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    job_fit: Mapped[float] = mapped_column(Float)
    report: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    profile_revision_id: Mapped[str] = mapped_column(String(32))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved | final | archived
    content: Mapped[dict] = mapped_column(JSON)
    change_log: Mapped[list] = mapped_column(JSON, default=list)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    revisions: Mapped[list[ResumeRevision]] = relationship(back_populates="version", cascade="all, delete-orphan",
                                                           order_by="ResumeRevision.iteration")
    files: Mapped[list[GeneratedFile]] = relationship(back_populates="version", cascade="all, delete-orphan")


class ResumeRevision(Base):
    """One cycle of the generate -> parse -> evaluate -> revise loop."""

    __tablename__ = "resume_revisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_version_id: Mapped[str] = mapped_column(ForeignKey("resume_versions.id", ondelete="CASCADE"), index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    diagnoses: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    version: Mapped[ResumeVersion] = relationship(back_populates="revisions")


class GeneratedFile(Base):
    __tablename__ = "generated_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    resume_version_id: Mapped[str] = mapped_column(ForeignKey("resume_versions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))  # pdf | docx | json | match_report | ...
    filename: Mapped[str] = mapped_column(String(200))
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    version: Mapped[ResumeVersion] = relationship(back_populates="files")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True, unique=True)
    resume_version_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="not_applied")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
