"""ORM models: tenants, API keys, research jobs, and reports.

IDs are string UUIDs (portable across Postgres and SQLite). JSON columns hold
semi-structured data (source lists, trace summaries) that we never query into.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Tenant(Base):
    """An isolated account/organization. All data is scoped to a tenant."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    api_keys: Mapped[list[ApiKey]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[ResearchJob]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    """A hashed API key belonging to a tenant.

    The raw key is shown to the user exactly once at creation. Only its SHA-256
    hash is stored; ``prefix`` is a non-secret label for display/lookup.
    """

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), default="default")
    prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped[Tenant] = relationship(back_populates="api_keys")


class ResearchJob(Base):
    """A single research run and its lifecycle."""

    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=JobStatus.QUEUED.value, index=True, nullable=False
    )
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metrics (also present in the trace, denormalized for quick listing).
    num_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trace: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    report: Mapped[Report | None] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )
    tenant: Mapped[Tenant] = relationship(back_populates="jobs")


class Report(Base):
    """The generated report for a job (markdown + rendered html + sources)."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    job: Mapped[ResearchJob] = relationship(back_populates="report")
