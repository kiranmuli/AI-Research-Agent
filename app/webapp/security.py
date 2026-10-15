"""Password hashing using PBKDF2-HMAC-SHA256 (Python standard library).

Chosen over bcrypt/argon2 so the app has no native build dependencies. The
stored string is self-describing: ``pbkdf2_sha256$<iterations>$<salt>$<hash>``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000
_SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()
    return f"{_ALGO}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$", 3)
        if algo != _ALGO:
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iters),
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(expected, digest)
