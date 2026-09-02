"""The background research task run by RQ workers.

This is the single unit of work the queue executes. It is import-safe and
self-contained: given a job id it loads context from the database, runs the
agent, streams progress to Redis, and persists the result.
"""

from __future__ import annotations

from app.db import repository as repo
from app.db.base import session_scope
from app.jobs.progress import publish
from app.llm.base import LLMError
from app.llm.factory import build_provider
from app.observability.logging import get_logger
from research_agent.agent import ResearchAgent
from research_agent.report import build_markdown_document, render_report_html

log = get_logger(__name__)


def run_research(job_id: str, topic: str, provider: str | None, model: str | None):
    """Execute a queued research job to completion.

    Any exception is caught, recorded on the job, and streamed to subscribers;
    the function never re-raises (a crash would just mark the RQ job failed
    without updating our own record).
    """
    log.info("job.start", job_id=job_id, topic=topic, provider=provider, model=model)

    with session_scope() as s:
        repo.mark_running(s, job_id)
    publish(job_id, "status", "running")

    def sink(line: str) -> None:
        publish(job_id, "log", line)

    try:
        llm = build_provider(provider=provider, model=model)
        ok, msg = llm.is_available()
        if not ok:
            raise LLMError(msg)

        agent = ResearchAgent(llm=llm)
        result = agent.research(topic, verbose=False, log_sink=sink)

        sources = [[s.title, s.url] for s in result.sources]
        markdown_doc = build_markdown_document(result.topic, result.report, sources)
        html = render_report_html(result.report)

        with session_scope() as s:
            repo.save_success(
                s,
                job_id,
                markdown=markdown_doc,
                html=html,
                sources=sources,
                trace=result.trace,
                num_sources=len(result.sources),
            )

        publish(
            job_id,
            "done",
            {
                "report_html": html,
                "sources": sources,
                "trace": result.trace,
                "num_sources": len(result.sources),
            },
        )
        log.info("job.done", job_id=job_id, num_sources=len(result.sources))
    except Exception as exc:  # noqa: BLE001 - record + surface, never re-raise
        message = str(exc)
        with session_scope() as s:
            repo.save_failure(s, job_id, message)
        publish(job_id, "error", message)
        log.error("job.failed", job_id=job_id, error=message)
    finally:
        publish(job_id, "end", None)
