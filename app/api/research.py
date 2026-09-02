"""Research REST API (v1).

Endpoints (all tenant-scoped via API key):
    POST   /api/v1/research              enqueue a job
    GET    /api/v1/research              list this tenant's jobs
    GET    /api/v1/research/<id>         job status + metadata
    GET    /api/v1/research/<id>/report  full report (json)
    GET    /api/v1/research/<id>/report.md   markdown download
    GET    /api/v1/research/<id>/report.pdf  pdf download
    GET    /api/v1/research/<id>/stream  live progress (SSE)
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, g, jsonify, request

from app.api.errors import ApiError
from app.api.extensions import limiter
from app.auth.guard import require_tenant
from app.db import repository as repo
from app.db.base import session_scope
from app.db.models import JobStatus
from app.jobs.connection import get_queue
from app.jobs.progress import subscribe
from app.observability.logging import get_logger
from app.observability.metrics import JOBS_TOTAL
from app.settings import get_settings
from research_agent.report import render_pdf_bytes

bp = Blueprint("research", __name__, url_prefix="/api/v1")
log = get_logger(__name__)

MAX_TOPIC_LEN = 500


def _job_to_dict(job) -> dict:
    return {
        "id": job.id,
        "topic": job.topic,
        "status": job.status,
        "provider": job.provider,
        "model": job.model,
        "error": job.error,
        "num_sources": job.num_sources,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@bp.post("/research")
@limiter.limit(lambda: get_settings().rate_limit_research)
@require_tenant
def create_research():
    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        raise ApiError("Field 'topic' is required.", 422)
    if len(topic) > MAX_TOPIC_LEN:
        raise ApiError(f"'topic' exceeds {MAX_TOPIC_LEN} characters.", 422)

    s = get_settings()
    provider = data.get("provider") or s.llm_provider
    model = data.get("model")  # None -> provider default

    with session_scope() as session:
        job = repo.create_job(
            session, g.tenant_id, topic, provider=provider, model=model
        )
        job_id = job.id
        payload = _job_to_dict(job)

    get_queue().enqueue(
        "app.jobs.tasks.run_research",
        job_id,
        topic,
        provider,
        model,
        job_id=job_id,
    )
    JOBS_TOTAL.labels(status="queued").inc()
    log.info("job.enqueued", job_id=job_id, tenant_id=g.tenant_id)

    return jsonify(payload), 202


@bp.get("/research")
@require_tenant
def list_research():
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = max(int(request.args.get("offset", 0)), 0)
    with session_scope() as session:
        jobs = repo.list_jobs(session, g.tenant_id, limit=limit, offset=offset)
        return jsonify(jobs=[_job_to_dict(j) for j in jobs])


@bp.get("/research/<job_id>")
@require_tenant
def get_research(job_id: str):
    with session_scope() as session:
        job = repo.get_job(session, job_id, g.tenant_id)
        if job is None:
            raise ApiError("Job not found.", 404)
        return jsonify(_job_to_dict(job))


@bp.get("/research/<job_id>/report")
@require_tenant
def get_report(job_id: str):
    with session_scope() as session:
        job = repo.get_job(session, job_id, g.tenant_id)
        if job is None:
            raise ApiError("Job not found.", 404)
        if job.report is None:
            raise ApiError(f"Report not ready (status: {job.status}).", 409)
        return jsonify(
            {
                **_job_to_dict(job),
                "markdown": job.report.markdown,
                "html": job.report.html,
                "sources": job.report.sources,
                "trace": job.trace,
            }
        )


@bp.get("/research/<job_id>/report.md")
@require_tenant
def download_markdown(job_id: str):
    with session_scope() as session:
        job = repo.get_job(session, job_id, g.tenant_id)
        if job is None or job.report is None:
            raise ApiError("Report not available.", 404)
        return Response(
            job.report.markdown,
            mimetype="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="report-{job_id}.md"'
            },
        )


@bp.get("/research/<job_id>/report.pdf")
@require_tenant
def download_pdf(job_id: str):
    with session_scope() as session:
        job = repo.get_job(session, job_id, g.tenant_id)
        if job is None or job.report is None:
            raise ApiError("Report not available.", 404)
        sources = [tuple(pair) for pair in job.report.sources]
        pdf = render_pdf_bytes(job.topic, job.report.markdown, sources)

    if pdf is None:
        raise ApiError("PDF could not be generated.", 500)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{job_id}.pdf"'
        },
    )


@bp.get("/research/<job_id>/stream")
@require_tenant
def stream_research(job_id: str):
    # Confirm the job belongs to this tenant before streaming.
    with session_scope() as session:
        job = repo.get_job(session, job_id, g.tenant_id)
        if job is None:
            raise ApiError("Job not found.", 404)
        terminal = job.status in (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value)
        snapshot = _job_to_dict(job)

    def generate():
        # If already finished, emit a single terminal event and stop.
        if terminal:
            yield _sse("status", snapshot["status"])
            yield _sse("end", None)
            return
        for event in subscribe(job_id):
            yield _sse(event["event"], event["data"])
        yield _sse("end", None)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
