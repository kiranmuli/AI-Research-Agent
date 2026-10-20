"""Tests for the FastAPI web app: auth, history, and chat-over-report.

Runs fully offline: SQLite, fakeredis, and a stub LLM provider.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from tests.conftest import StubLLM


@pytest.fixture()
def webclient(db, fake_redis, monkeypatch):
    # Ground chat + assistant on a deterministic provider (no network / model).
    import app.services.assistant as assistant_mod
    import app.services.chat as chat_mod
    import app.webapp.routers.openai_compat as oai_mod

    monkeypatch.setattr(chat_mod, "get_provider", lambda *a, **k: StubLLM())
    monkeypatch.setattr(assistant_mod, "get_provider", lambda *a, **k: StubLLM())
    monkeypatch.setattr(oai_mod, "get_provider", lambda *a, **k: StubLLM())

    from app.webapp import create_app

    app = create_app()
    # Don't auto-follow redirects so we can assert on 303s.
    return TestClient(app, follow_redirects=False)


def _signup(client, email="a@b.com", password="supersecret"):
    return client.post(
        "/signup",
        data={"email": email, "password": password, "next": "/"},
    )


def test_home_requires_login(webclient):
    r = webclient.get("/")
    assert r.status_code == 303
    assert "/login" in r.headers["location"]


def test_signup_then_chat_home(webclient):
    r = _signup(webclient)
    assert r.status_code == 303 and r.headers["location"] == "/"
    # Session cookie now set → chat home renders.
    r = webclient.get("/", follow_redirects=True)
    assert r.status_code == 200
    assert "How can I help" in r.text


def test_research_dashboard(webclient):
    _signup(webclient, email="rd@e.com", password="researchpass")
    r = webclient.get("/research", follow_redirects=True)
    assert r.status_code == 200
    assert "Research anything" in r.text


def test_new_conversation_and_stream(webclient):
    _signup(webclient, email="chatapp@e.com", password="chatapppass")
    r = webclient.post("/api/conversations")
    assert r.status_code == 200
    cid = r.json()["id"]

    r = webclient.post(
        f"/api/conversations/{cid}/message", json={"message": "hi there"}
    )
    assert r.status_code == 200
    assert "stub assistant" in r.text  # streamed reply body

    # Both turns persisted; title derived from the first user message.
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        msgs = repo.list_messages(s, cid)
        convo = repo.get_conversation(s, cid)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert convo.title.startswith("hi there")


def test_delete_conversation(webclient):
    _signup(webclient, email="del@e.com", password="deletepass1")
    cid = webclient.post("/api/conversations").json()["id"]
    r = webclient.request("DELETE", f"/api/conversations/{cid}")
    assert r.status_code == 200
    assert webclient.get("/api/conversations").json()["conversations"] == []


def test_duplicate_signup_rejected(webclient):
    _signup(webclient)
    webclient.post("/logout")
    r = _signup(webclient)
    assert r.status_code == 422
    assert "already exists" in r.text


def test_login_bad_password(webclient):
    _signup(webclient, email="c@d.com", password="rightpassword")
    webclient.post("/logout")
    r = webclient.post(
        "/login", data={"email": "c@d.com", "password": "wrongpassword", "next": "/"}
    )
    assert r.status_code == 401
    assert "Invalid email or password" in r.text


def test_history_lists_users_jobs(webclient, db):
    _signup(webclient, email="h@i.com", password="historypass")
    # Seed a finished job + report directly for this user.
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        user = repo.get_user_by_email(s, "h@i.com")
        job = repo.create_job(
            s, user.tenant_id, "coffee and sleep", user_id=user.id
        )
        repo.save_success(
            s, job.id, markdown="# R\n\nText [1].", html="<h1>R</h1>",
            sources=[["Src", "https://x.test"]], trace={}, num_sources=1,
        )

    r = webclient.get("/research", follow_redirects=True)
    assert "coffee and sleep" in r.text


def test_chat_over_report(webclient, db):
    _signup(webclient, email="chat@e.com", password="chatpass123")
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        user = repo.get_user_by_email(s, "chat@e.com")
        job = repo.create_job(s, user.tenant_id, "green tea", user_id=user.id)
        repo.save_success(
            s, job.id, markdown="# Green tea\n\nIt has antioxidants [1].",
            html="<p>antioxidants</p>", sources=[["S", "https://x.test"]],
            trace={}, num_sources=1,
        )
        job_id = job.id

    # Open chat page → creates the conversation.
    r = webclient.get(f"/chat/{job_id}", follow_redirects=True)
    assert r.status_code == 200

    from app.db.base import session_scope as ss

    with ss() as s:
        user = repo.get_user_by_email(s, "chat@e.com")
        convo = repo.get_conversation_for_job(s, job_id, user.id)
        convo_id = convo.id

    r = webclient.post(f"/api/chat/{convo_id}", json={"message": "What's in it?"})
    assert r.status_code == 200
    assert r.json()["answer"]

    # The turn is persisted (question + answer).
    with ss() as s:
        msgs = repo.list_messages(s, convo_id)
    assert len(msgs) == 2
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"


def _make_api_key():
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        t = repo.create_tenant(s, "OAI Co")
        _, raw = repo.create_api_key(s, t.id, "oai")
    return raw


def test_openai_compat_requires_key(webclient):
    r = webclient.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 401


def test_openai_compat_chat_completion(webclient):
    key = _make_api_key()
    r = webclient.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "any-model",
            "messages": [
                {"role": "system", "content": "be nice"},
                {"role": "user", "content": "hello"},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["object"] == "chat.completion"
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "stub assistant" in data["choices"][0]["message"]["content"]


def test_openai_compat_streaming(webclient):
    key = _make_api_key()
    r = webclient.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )
    assert r.status_code == 200
    body = r.text
    assert "chat.completion.chunk" in body
    assert "data: [DONE]" in body


def test_openai_compat_models(webclient):
    key = _make_api_key()
    r = webclient.get("/v1/models", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    assert r.json()["data"][0]["id"]


def test_cannot_chat_without_report(webclient, db):
    _signup(webclient, email="nr@e.com", password="noreport123")
    from app.db import repository as repo
    from app.db.base import session_scope

    with session_scope() as s:
        user = repo.get_user_by_email(s, "nr@e.com")
        job = repo.create_job(s, user.tenant_id, "pending topic", user_id=user.id)
        job_id = job.id

    # No report yet → chat page redirects back to the report view.
    r = webclient.get(f"/chat/{job_id}")
    assert r.status_code == 303
    assert f"/research/{job_id}" in r.headers["location"]
