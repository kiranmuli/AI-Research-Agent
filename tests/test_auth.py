from app.auth import keys


def test_key_generation_and_hashing():
    raw = keys.generate_key()
    assert raw.startswith("rak_")
    assert keys.key_prefix(raw) == raw[:12]
    assert keys.hash_key(raw) == keys.hash_key(raw)  # deterministic
    assert keys.verify(raw, keys.hash_key(raw))
    assert not keys.verify("rak_wrong", keys.hash_key(raw))


def test_authenticate_roundtrip(tenant):
    from app.db import repository as repo
    from app.db.base import session_scope

    tenant_id, raw = tenant
    with session_scope() as s:
        found = repo.authenticate(s, raw)
        assert found is not None and found.id == tenant_id
        assert repo.authenticate(s, "rak_bogus") is None


def test_revoked_key_rejected(tenant):
    from sqlalchemy import select

    from app.db import repository as repo
    from app.db.base import session_scope
    from app.db.models import ApiKey

    tenant_id, raw = tenant
    with session_scope() as s:
        key_id = s.scalar(select(ApiKey).where(ApiKey.tenant_id == tenant_id)).id
        assert repo.revoke_api_key(s, tenant_id, key_id)
    with session_scope() as s:
        assert repo.authenticate(s, raw) is None
