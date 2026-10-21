"""FastAPI application factory."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.db.base import get_engine
from app.jobs.connection import get_redis
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import (
    HTTP_LATENCY,
    HTTP_REQUESTS,
    metrics_response,
)
from app.settings import get_settings
from app.webapp.deps import LoginRequired
from app.webapp.routers import (
    assistant,
    auth,
    chat,
    openai_compat,
    pages,
    research,
)

log = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging()

    app = FastAPI(
        title="AI Research Agent",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        SessionMiddleware,
        secret_key=s.secret_key,
        session_cookie=s.session_cookie_name,
        max_age=s.session_max_age,
        https_only=s.session_cookie_secure,
        same_site="lax",
    )

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(auth.router)
    app.include_router(assistant.router)
    app.include_router(pages.router)
    app.include_router(research.router)
    app.include_router(chat.router)
    app.include_router(openai_compat.router)

    _register_infra(app)

    log.info(
        "webapp.created",
        environment=s.environment,
        provider=s.llm_provider,
        model=s.active_model(),
    )
    return app


def _register_infra(app: FastAPI) -> None:
    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired):
        # Browser requests → redirect to the login page; API clients → 401.
        if request.url.path.startswith("/api/"):
            return PlainTextResponse("Authentication required", status_code=401)
        nxt = request.url.path
        target = f"/login?next={nxt}" if nxt and nxt != "/" else "/login"
        return RedirectResponse(target, status_code=303)

    @app.middleware("http")
    async def _observe(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        try:
            endpoint = request.scope.get("route")
            name = getattr(endpoint, "path", request.url.path)
            HTTP_REQUESTS.labels(
                method=request.method, endpoint=name, status=response.status_code
            ).inc()
            HTTP_LATENCY.labels(method=request.method, endpoint=name).observe(
                time.perf_counter() - start
            )
        except Exception:  # noqa: BLE001 - never break a response over metrics
            pass
        return response

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/readyz", include_in_schema=False)
    async def readyz():
        checks = {"database": "ok", "redis": "ok"}
        status = "ok"
        try:
            from sqlalchemy import text

            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            checks["database"] = f"error: {exc}"
            status = "error"
        try:
            get_redis().ping()
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"
            status = "error"
        code = 200 if status == "ok" else 503
        return Response(
            content=_json({"status": status, "checks": checks}),
            media_type="application/json",
            status_code=code,
        )

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        body, content_type = metrics_response()
        return Response(content=body, media_type=content_type)


def _json(obj) -> str:
    import json

    return json.dumps(obj)
