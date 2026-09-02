from app.db import repository as repo
from app.db.base import session_scope
from app.db.models import JobStatus


def test_job_lifecycle(tenant):
    tenant_id, _ = tenant
    with session_scope() as s:
        job = repo.create_job(s, tenant_id, "topic", "ollama", "llama3.2")
        jid = job.id
        assert job.status == JobStatus.QUEUED.value

    with session_scope() as s:
        repo.mark_running(s, jid)
    with session_scope() as s:
        assert repo.get_job(s, jid).status == JobStatus.RUNNING.value

    with session_scope() as s:
        repo.save_success(s, jid, "# md", "<h1>", [["t", "u"]], {"x": 1}, 1)
    with session_scope() as s:
        job = repo.get_job(s, jid, tenant_id)
        assert job.status == JobStatus.SUCCEEDED.value
        assert job.report.markdown == "# md"
        assert job.num_sources == 1


def test_tenant_isolation(tenant):
    tenant_id, _ = tenant
    with session_scope() as s:
        other = repo.create_tenant(s, "Other")
        job = repo.create_job(s, tenant_id, "topic")
        jid, other_id = job.id, other.id
    with session_scope() as s:
        # Wrong tenant cannot see the job.
        assert repo.get_job(s, jid, other_id) is None
        assert repo.get_job(s, jid, tenant_id) is not None


def test_failure_recorded(tenant):
    tenant_id, _ = tenant
    with session_scope() as s:
        jid = repo.create_job(s, tenant_id, "topic").id
    with session_scope() as s:
        repo.save_failure(s, jid, "boom")
    with session_scope() as s:
        job = repo.get_job(s, jid)
        assert job.status == JobStatus.FAILED.value
        assert job.error == "boom"
