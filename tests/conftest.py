"""Shared pytest fixtures.

Everything runs without external services: SQLite replaces Postgres, fakeredis
replaces Redis, and a stub LLM provider replaces network/model calls.
"""

from __future__ import annotations

import os

import fakeredis
import pytest

# Configure the environment BEFORE app modules read settings.
os.environ.setdefault("REQUIRE_API_KEY", "true")
os.environ.setdefault("RATE_LIMIT_DEFAULT", "10000/minute")
os.environ.setdefault("RATE_LIMIT_RESEARCH", "10000/minute")
os.environ.setdefault("LOG_JSON", "false")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Fresh SQLite database per test."""
    import app.settings as settings_mod
    from app.db import base as db_base

    url = f"sqlite:///{tmp_path/'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    settings_mod.get_settings.cache_clear()
    db_base.reset_engine_cache()

    db_base.create_all()
    yield
    db_base.reset_engine_cache()
    settings_mod.get_settings.cache_clear()


@pytest.fixture()
def fake_redis(monkeypatch):
    """Patch the Redis singleton with an in-memory fake."""
    from app.jobs import connection

    server = fakeredis.FakeServer()
    fake = fakeredis.FakeStrictRedis(server=server)
    connection.get_redis.cache_clear()
    connection.get_queue.cache_clear()
    monkeypatch.setattr(connection, "get_redis", lambda: fake)
    yield fake


@pytest.fixture()
def tenant(db):
    """Create a tenant and an API key; returns (tenant_id, raw_key)."""
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        t = repo.create_tenant(s, "Test Co")
        _, raw = repo.create_api_key(s, t.id, "test")
        tid = t.id
    return tid, raw


@pytest.fixture()
def client(db, fake_redis, monkeypatch):
    """Flask test client with limiter using in-memory storage."""
    import app.settings as settings_mod

    s = settings_mod.get_settings()
    object.__setattr__(s, "redis_url", "memory://")

    from app.api.app import create_app

    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


class StubLLM:
    """Deterministic LLM provider for tests (no network, no model)."""

    provider_name = "stub"
    model = "stub-model"

    def __init__(self, available=True):
        self._available = available

    def chat_with_tokens(self, system, user, temperature=0.2):
        if "search queries" in user or "queries" in system.lower():
            return "query one\nquery two", {"prompt": 10, "output": 5}
        return "# Findings\n\nA cited summary [1].", {"prompt": 100, "output": 40}

    def chat(self, system, user, temperature=0.2):
        return self.chat_with_tokens(system, user, temperature)[0]

    def is_available(self):
        return (self._available, "ok" if self._available else "unavailable")
