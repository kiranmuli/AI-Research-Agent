"""Data-access helpers.

Thin functions over the ORM so the API/queue layers never write raw queries.
All job/report access is tenant-scoped to enforce multi-tenant isolation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import keys
from app.db.models import (
    ApiKey,
    ChatMessage,
    Conversation,
    JobStatus,
    Report,
    ResearchJob,
    Tenant,
    User,
)


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
    user_id: str | None = None,
) -> ResearchJob:
    job = ResearchJob(
        tenant_id=tenant_id,
        topic=topic,
        status=JobStatus.QUEUED.value,
        provider=provider,
        model=model,
        user_id=user_id,
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


# --- users ---------------------------------------------------------------

def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.lower().strip()))


def get_user(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def create_user(session: Session, email: str, password_hash: str) -> User:
    """Create a user and the private tenant that scopes all their data."""
    tenant = create_tenant(session, f"user:{email.lower().strip()}")
    user = User(
        tenant_id=tenant.id,
        email=email.lower().strip(),
        password_hash=password_hash,
    )
    session.add(user)
    session.flush()
    return user


def touch_user_login(session: Session, user_id: str) -> None:
    user = session.get(User, user_id)
    if user is not None:
        user.last_login_at = _now()


# --- conversations & chat ------------------------------------------------

def create_conversation(
    session: Session, user_id: str, job_id: str, title: str = ""
) -> Conversation:
    convo = Conversation(user_id=user_id, job_id=job_id, title=title[:500])
    session.add(convo)
    session.flush()
    return convo


def get_conversation(
    session: Session, conversation_id: str, user_id: str | None = None
) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    if user_id is not None:
        stmt = stmt.where(Conversation.user_id == user_id)
    return session.scalar(stmt)


def get_conversation_for_job(
    session: Session, job_id: str, user_id: str
) -> Conversation | None:
    """Return the user's existing conversation for a job, if any."""
    return session.scalar(
        select(Conversation)
        .where(Conversation.job_id == job_id, Conversation.user_id == user_id)
        .order_by(Conversation.created_at.asc())
        .limit(1)
    )


def list_messages(session: Session, conversation_id: str) -> list[ChatMessage]:
    return list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
    )


def add_message(
    session: Session, conversation_id: str, role: str, content: str
) -> ChatMessage:
    msg = ChatMessage(
        conversation_id=conversation_id, role=role, content=content
    )
    session.add(msg)
    session.flush()
    return msg


def count_jobs(session: Session, tenant_id: str) -> int:
    return int(
        session.scalar(
            select(func.count(ResearchJob.id)).where(
                ResearchJob.tenant_id == tenant_id
            )
        )
        or 0
    )
