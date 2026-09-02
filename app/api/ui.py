"""Browser UI blueprint.

Humans use this page (behind your own network/proxy); it does not require an API
key and operates under a shared "default" tenant. It enqueues a job on the same
queue the API uses and streams live progress over SSE via Redis pub/sub.
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, render_template, request

from app.auth.guard import _default_tenant_id
from app.db import repository as repo
from app.db.base import session_scope
from app.jobs.connection import get_queue
from app.jobs.progress import subscribe
from app.settings import get_settings
from research_agent.report import render_pdf_bytes

bp = Blueprint("ui", __name__)


@bp.get("/")
def index():
    s = get_settings()
    return render_template(
        "index.html", model=s.active_model(), provider=s.llm_provider
    )


@bp.get("/research")
def research_stream():
    topic = (request.args.get("topic") or "").strip()

    def generate():
        if not topic:
            yield _sse("error", "Please enter a topic to research.")
            return

        s = get_settings()
        tenant_id = _default_tenant_id()
        with session_scope() as session:
            job = repo.create_job(
                session, tenant_id, topic, provider=s.llm_provider, model=None
            )
            job_id = job.id

        get_queue().enqueue(
            "app.jobs.tasks.run_research",
            job_id,
            topic,
            s.llm_provider,
            None,
            job_id=job_id,
        )

        for event in subscribe(job_id):
            name = event["event"]
            data = event["data"]
            if name == "done":
                # Point the browser at the DB-backed download endpoints.
                data = {
                    **(data or {}),
                    "id": job_id,
                    "md": f"/ui/report/{job_id}.md",
                    "pdf": f"/ui/report/{job_id}.pdf",
                }
            yield _sse(name, data)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return Response(generate(), mimetype="text/event-stream", headers=headers)


@bp.get("/ui/report/<job_id>.md")
def ui_markdown(job_id: str):
    tenant_id = _default_tenant_id()
    with session_scope() as session:
        job = repo.get_job(session, job_id, tenant_id)
        if job is None or job.report is None:
            return Response("Not found", status=404)
        return Response(
            job.report.markdown,
            mimetype="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="report-{job_id}.md"'
            },
        )


@bp.get("/ui/report/<job_id>.pdf")
def ui_pdf(job_id: str):
    tenant_id = _default_tenant_id()
    with session_scope() as session:
        job = repo.get_job(session, job_id, tenant_id)
        if job is None or job.report is None:
            return Response("Not found", status=404)
        sources = [tuple(pair) for pair in job.report.sources]
        pdf = render_pdf_bytes(job.topic, job.report.markdown, sources)
    if pdf is None:
        return Response("PDF unavailable", status=404)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{job_id}.pdf"'
        },
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
