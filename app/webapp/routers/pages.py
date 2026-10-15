"""HTML pages: dashboard (new research + history) and the report view."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.models import JobStatus, User
from app.settings import get_settings
from app.webapp.deps import get_db, require_user
from app.webapp.templating import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    jobs = repo.list_jobs(db, user.tenant_id, limit=100)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "jobs": jobs,
            "total": repo.count_jobs(db, user.tenant_id),
            "default_model": get_settings().active_model(),
        },
    )


@router.get("/research/{job_id}", response_class=HTMLResponse)
async def report_page(
    request: Request,
    job_id: str,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = repo.get_job(db, job_id, user.tenant_id)
    if job is None:
        return templates.TemplateResponse(
            request,
            "not_found.html",
            {"user": user},
            status_code=404,
        )
    report = job.report
    done = job.status in (JobStatus.SUCCEEDED.value, JobStatus.FAILED.value)
    convo = repo.get_conversation_for_job(db, job.id, user.id)
    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "user": user,
            "job": job,
            "report": report,
            "done": done,
            "conversation_id": convo.id if convo else None,
            "trace": job.trace or {},
        },
    )
