"""Health, readiness, and metrics endpoints (unauthenticated)."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

from app import __version__
from app.observability.metrics import metrics_response
from app.settings import get_settings

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    """Liveness: the process is up. Never touches external deps."""
    return jsonify(status="ok", version=__version__)


@bp.get("/readyz")
def readyz():
    """Readiness: dependencies (DB, Redis) are reachable."""
    checks: dict[str, str] = {}
    ok = True

    try:
        from sqlalchemy import text

        from app.db.base import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        checks["database"] = f"error: {exc}"
        ok = False

    try:
        from app.jobs.connection import get_redis

        get_redis().ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"
        ok = False

    return jsonify(status="ok" if ok else "degraded", checks=checks), (
        200 if ok else 503
    )


@bp.get("/metrics")
def metrics():
    if not get_settings().metrics_enabled:
        return jsonify(error="metrics disabled"), 404
    body, content_type = metrics_response()
    return Response(body, mimetype=content_type)
