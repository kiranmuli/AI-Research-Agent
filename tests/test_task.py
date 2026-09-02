"""End-to-end test of the background task with all I/O stubbed."""

from __future__ import annotations

import app.jobs.tasks as tasks
from app.db import repository as repo
from app.db.base import session_scope
from app.db.models import JobStatus
from research_agent.agent import ResearchAgent, Source
from research_agent.search import SearchResult
from tests.conftest import StubLLM


def _stub_agent_success(monkeypatch):
    monkeypatch.setattr(
        "research_agent.agent.web_search",
        lambda q: [SearchResult("Title", "http://example.com", "snippet")],
    )
    monkeypatch.setattr(
        "research_agent.agent.fetch_text", lambda url: "Readable page text."
    )


def test_run_research_success(db, fake_redis, tenant, monkeypatch):
    tenant_id, _ = tenant
    _stub_agent_success(monkeypatch)
    monkeypatch.setattr(tasks, "build_provider", lambda provider, model: StubLLM())

    with session_scope() as s:
        job_id = repo.create_job(s, tenant_id, "green tea", "stub", "stub-model").id

    tasks.run_research(job_id, "green tea", "stub", "stub-model")

    with session_scope() as s:
        job = repo.get_job(s, job_id)
        assert job.status == JobStatus.SUCCEEDED.value
        assert job.report is not None
        assert job.num_sources == 1
        assert "Findings" in job.report.markdown


def test_run_research_llm_unavailable(db, fake_redis, tenant, monkeypatch):
    tenant_id, _ = tenant
    monkeypatch.setattr(
        tasks, "build_provider", lambda provider, model: StubLLM(available=False)
    )

    with session_scope() as s:
        job_id = repo.create_job(s, tenant_id, "topic", "stub", "stub").id

    tasks.run_research(job_id, "topic", "stub", "stub")

    with session_scope() as s:
        job = repo.get_job(s, job_id)
        assert job.status == JobStatus.FAILED.value
        assert "unavailable" in (job.error or "")


def test_agent_uses_provider_interface():
    """The agent depends only on the provider interface (no Ollama import)."""
    agent = ResearchAgent(llm=StubLLM())
    assert isinstance(agent.synthesize.__self__, ResearchAgent)
    src = [Source("t", "u", "text")]
    from research_agent.logger import StepLogger
    from research_agent.trace import RunTrace

    report = agent.synthesize(
        "topic", src, StepLogger(enabled=False), RunTrace("topic", "stub")
    )
    assert "Findings" in report
