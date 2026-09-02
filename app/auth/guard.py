"""Request-level authentication guard for the REST API.

Extracts the API key from ``Authorization: Bearer <key>`` (or the ``X-API-Key``
header), resolves it to a tenant, and stores the tenant on Flask's ``g``. Use
the :func:`require_tenant` decorator on protected endpoints.
"""

from __future__ import annotations

import functools

from flask import g, jsonify, request

from app.db import repository as repo
from app.db.base import session_scope
from app.settings import get_settings


def _extract_key() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("X-API-Key") or None


def current_tenant_id() -> str | None:
    return getattr(g, "tenant_id", None)


def require_tenant(fn):
    """Decorator: reject requests without a valid API key.

    When ``REQUIRE_API_KEY`` is disabled (single-tenant/dev), requests fall back
    to a shared default tenant so the API still works without keys.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        s = get_settings()
        raw = _extract_key()

        if not s.require_api_key and not raw:
            # Dev/single-tenant mode: use (or lazily create) a default tenant.
            g.tenant_id = _default_tenant_id()
            return fn(*args, **kwargs)

        if not raw:
            return jsonify(error="Missing API key"), 401

        with session_scope() as session:
            tenant = repo.authenticate(session, raw)
            if tenant is None:
                return jsonify(error="Invalid or revoked API key"), 401
            g.tenant_id = tenant.id

        return fn(*args, **kwargs)

    return wrapper


def _default_tenant_id() -> str:
    """Return a stable default tenant id, creating it once if needed."""
    from sqlalchemy import select

    from app.db.models import Tenant

    with session_scope() as session:
        tenant = session.scalar(select(Tenant).where(Tenant.name == "default"))
        if tenant is None:
            tenant = repo.create_tenant(session, "default")
            session.flush()
        return tenant.id
