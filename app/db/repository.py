"""Data-access helpers.

Thin functions over the ORM so the API/queue layers never write raw queries.
All job/report access is tenant-scoped to enforce multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import keys
from app.db.models import ApiKey, JobStatus, Report, ResearchJob, Tenant


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- tenants & keys ------------------------------------------------------

def create_tenant(session: Session, name: str) -> Tenant:
    tenant = Tenant(name=name)
    session.add(tenant)
    session.flush()
    return tenant


def create_api_key(
    session: Session, tenant_id: str, name: str = "default"
) -> tuple[ApiKey, str]:
    """Create a key for a tenant; returns ``(record, raw_key)``.

    The raw key is only available here — it is never recoverable later.
    """
    raw = keys.generate_key()
    record = ApiKey(
        tenant_id=tenant_id,
        name=name,
        prefix=keys.key_prefix(raw),
        key_hash=keys.hash_key(raw),
    )
    session.add(record)
    session.flush()
    return record, raw


def authenticate(session: Session, raw_key: str) -> Tenant | None:
    """Resolve a raw API key to its tenant, or ``None`` if invalid/revoked.

    Updates ``last_used_at`` on success.
    """
    if not raw_key:
        return None
    key_hash = keys.hash_key(raw_key)
    record = session.scalar(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
    )
    if record is None:
        return None
    record.last_used_at = _now()
    return record.tenant


def revoke_api_key(session: Session, tenant_id: str, key_id: str) -> bool:
    record = session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
    )
    if record is None:
        return False
    record.revoked = True
    return True


# --- jobs ----------------------------------------------------------------

def create_job(
    session: Session,
    tenant_id: str,
    topic: str,
    provider: str | None = None,
    model: str | None = None,
) -> ResearchJob:
    job = ResearchJob(
        tenant_id=tenant_id,
        topic=topic,
        status=JobStatus.QUEUED.value,
        provider=provider,
        model=model,
    )
    session.add(job)
    session.flush()
    return job


def get_job(
    session: Session, job_id: str, tenant_id: str | None = None
) -> ResearchJob | None:
    stmt = select(ResearchJob).where(ResearchJob.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(ResearchJob.tenant_id == tenant_id)
    return session.scalar(stmt)


def list_jobs(
    session: Session, tenant_id: str, limit: int = 50, offset: int = 0
) -> list[ResearchJob]:
    stmt = (
        select(ResearchJob)
        .where(ResearchJob.tenant_id == tenant_id)
        .order_by(ResearchJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt))


def mark_running(session: Session, job_id: str) -> None:
    job = session.get(ResearchJob, job_id)
    if job is not None:
        job.status = JobStatus.RUNNING.value
        job.started_at = _now()


def save_success(
    session: Session,
    job_id: str,
    markdown: str,
    html: str,
    sources: list,
    trace: dict | None,
    num_sources: int,
) -> None:
    job = session.get(ResearchJob, job_id)
    if job is None:
        return
    job.status = JobStatus.SUCCEEDED.value
    job.finished_at = _now()
    job.trace = trace
    job.num_sources = num_sources
    job.report = Report(
        job_id=job.id, markdown=markdown, html=html, sources=sources
    )


def save_failure(session: Session, job_id: str, error: str) -> None:
    job = session.get(ResearchJob, job_id)
    if job is None:
        return
    job.status = JobStatus.FAILED.value
    job.finished_at = _now()
    job.error = error
