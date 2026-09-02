"""Application factory: assembles settings, logging, rate limiting, metrics,
error handling, and all blueprints into a configured Flask app.
"""

from __future__ import annotations

import time

from flask import Flask, g, request

from app.api.errors import register_error_handlers
from app.api.extensions import limiter
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.settings import get_settings

log = get_logger(__name__)


def create_app() -> Flask:
    s = get_settings()
    configure_logging()

    app = Flask(__name__, template_folder="../../templates")
    app.config.update(
        SECRET_KEY=s.secret_key,
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,  # 1 MB request cap
        # Rate limiting (Redis-backed so limits are shared across workers).
        RATELIMIT_STORAGE_URI=s.redis_url,
        RATELIMIT_DEFAULT=s.rate_limit_default,
        RATELIMIT_STRATEGY="fixed-window",
        RATELIMIT_HEADERS_ENABLED=True,
    )
    limiter.init_app(app)

    # --- blueprints (views attach their own per-route limits at import) ---
    from app.api.health import bp as health_bp
    from app.api.research import bp as research_bp
    from app.api.ui import bp as ui_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(ui_bp)

    # Health/metrics probes should never be rate limited.
    limiter.exempt(health_bp)

    register_error_handlers(app)
    _register_observability(app)

    log.info(
        "app.created",
        environment=s.environment,
        provider=s.llm_provider,
        model=s.active_model(),
    )
    return app


def _register_observability(app: Flask) -> None:
    @app.before_request
    def _start_timer():
        g._start = time.perf_counter()

    @app.after_request
    def _record(response):
        try:
            endpoint = request.endpoint or "unknown"
            HTTP_REQUESTS.labels(
                method=request.method, endpoint=endpoint, status=response.status_code
            ).inc()
            if hasattr(g, "_start"):
                HTTP_LATENCY.labels(
                    method=request.method, endpoint=endpoint
                ).observe(time.perf_counter() - g._start)
        except Exception:  # noqa: BLE001 - never break a response over metrics
            pass
        return response
