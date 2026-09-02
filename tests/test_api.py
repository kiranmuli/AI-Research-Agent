def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"http_requests_total" in r.data


def test_research_requires_api_key(client):
    r = client.post("/api/v1/research", json={"topic": "x"})
    assert r.status_code == 401


def test_create_and_get_job(client, tenant, fake_redis):
    _, raw = tenant
    headers = {"Authorization": f"Bearer {raw}"}

    r = client.post("/api/v1/research", json={"topic": "quantum"}, headers=headers)
    assert r.status_code == 202
    job = r.get_json()
    assert job["status"] == "queued"
    assert job["topic"] == "quantum"

    r = client.get(f"/api/v1/research/{job['id']}", headers=headers)
    assert r.status_code == 200

    r = client.get("/api/v1/research", headers=headers)
    assert r.get_json()["jobs"][0]["id"] == job["id"]


def test_missing_topic_is_422(client, tenant):
    _, raw = tenant
    r = client.post(
        "/api/v1/research", json={}, headers={"Authorization": f"Bearer {raw}"}
    )
    assert r.status_code == 422


def test_research_rate_limited(db, fake_redis, tenant, monkeypatch):
    import app.settings as settings_mod
    from app.api.app import create_app

    s = settings_mod.get_settings()
    object.__setattr__(s, "redis_url", "memory://")
    object.__setattr__(s, "rate_limit_research", "2/minute")
    object.__setattr__(s, "rate_limit_default", "1000/minute")

    app = create_app()
    app.config.update(TESTING=True)
    c = app.test_client()

    _, raw = tenant
    h = {"Authorization": f"Bearer {raw}"}
    codes = [c.post("/api/v1/research", json={"topic": "t"}, headers=h).status_code
             for _ in range(4)]
    assert codes.count(202) == 2
    assert 429 in codes


def test_cross_tenant_job_hidden(client, tenant, fake_redis):
    from app.db import repository as repo
    from app.db.base import session_scope

    _, raw = tenant
    r = client.post(
        "/api/v1/research",
        json={"topic": "secret"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    job_id = r.get_json()["id"]

    with session_scope() as s:
        other = repo.create_tenant(s, "Other")
        _, other_raw = repo.create_api_key(s, other.id, "k")

    r = client.get(
        f"/api/v1/research/{job_id}",
        headers={"Authorization": f"Bearer {other_raw}"},
    )
    assert r.status_code == 404
