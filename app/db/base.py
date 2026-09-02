"""SQLAlchemy engine and session management.

The engine is created lazily from ``settings.database_url`` so importing this
module never requires a live database (tests and tooling can import models and
metadata freely). Postgres is the production target; SQLite is used in tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = get_settings()
    url = s.database_url
    # SQLite (tests) needs a couple of connect args to behave with threads.
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
        echo=s.debug and not s.is_production,
    )


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def get_session() -> Session:
    """Return a new session. Caller is responsible for closing it."""
    return _session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on error."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all() -> None:
    """Create all tables (used in dev/tests; production uses Alembic)."""
    # Import models so they register on Base.metadata before create_all.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def reset_engine_cache() -> None:
    """Drop cached engine/session factory (used by tests to switch DBs)."""
    get_engine.cache_clear()
    _session_factory.cache_clear()
