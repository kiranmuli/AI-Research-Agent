"""Research actions for signed-in users: start jobs, poll status, stream
progress, and download reports. Jobs are scoped to the user's tenant.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form
from fastapi.responses import (
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from sqlalchemy.orm import Session
from starlette.concurrency import iterate_in_threadpool

from app.db import repository as repo
from app.db.models import JobStatus, User
from app.jobs.connection import get_queue
from app.jobs.progress import subscribe
from app.observability.logging import get_logger
from app.observability.metrics import JOBS_TOTAL
from app.settings import get_settings
from app.webapp.deps import get_db, require_user
from research_agent.report import render_pdf_bytes

router = APIRouter()
log = get_logger(__name__)

MAX_TOPIC_LEN = 500


def job_to_dict(job) -> dict:
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


@router.post("/research")
async def start_research(
    topic: str = Form(...),
    model: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    topic = topic.strip()
    if not topic:
        return RedirectResponse("/?error=empty", status_code=303)
    topic = topic[:MAX_TOPIC_LEN]

    s = get_settings()
    provider = s.llm_provider
    model_val = model.strip() or None

    job = repo.create_job(
        db,
        user.tenant_id,
        topic,
        provider=provider,
        model=model_val,
        user_id=user.id,
    )
    job_id = job.id
    db.commit()

    get_queue().enqueue(
        "app.jobs.tasks.run_research",
        job_id,
        topic,
        provider,
        model_val,
        job_id=job_id,
    )
    JOBS_TOTAL.labels(status="queued").inc()
    log.info("job.enqueued", job_id=job_id, user_id=user.id)
    return RedirectResponse(f"/research/{job_id}", status_code=303)


@router.get("/api/research/{job_id}")
async def job_status(
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return job_to_dict(job)


@router.get("/api/research/{job_id}/stream")
async def stream(
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    terminal = job.status in (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value)
    status_val = job.status

    def generate():
        if terminal:
            yield _sse("status", status_val)
            yield _sse("end", None)
            return
        for event in subscribe(job_id):
            yield _sse(event["event"], event["data"])
        yield _sse("end", None)

    return StreamingResponse(
        iterate_in_threadpool(generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/research/{job_id}/report.md")
async def download_markdown(
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None or job.report is None:
        return Response("Report not available.", status_code=404)
    return Response(
        job.report.markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="report-{job_id}.md"'
        },
    )


@router.get("/research/{job_id}/report.pdf")
async def download_pdf(
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None or job.report is None:
        return Response("Report not available.", status_code=404)
    sources = [tuple(pair) for pair in job.report.sources]
    pdf = render_pdf_bytes(job.topic, job.report.markdown, sources)
    if pdf is None:
        return Response("PDF could not be generated.", status_code=500)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{job_id}.pdf"'
        },
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
