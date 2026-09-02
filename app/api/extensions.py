"""Flask extensions instantiated at import time and bound in the app factory.

Defining the limiter here (rather than inside ``create_app``) lets view
functions attach specific limits with ``@limiter.limit(...)`` at definition
time — the only way per-route limits reliably register with the endpoint.
"""

from __future__ import annotations

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def rate_limit_key() -> str:
    """Rate-limit per API key when present, else per client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()[:32]
    return request.headers.get("X-API-Key", "") or get_remote_address()


limiter = Limiter(key_func=rate_limit_key)
