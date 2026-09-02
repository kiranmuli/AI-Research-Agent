"""API-key generation and hashing.

Keys look like ``rak_<40 url-safe chars>``. Only the SHA-256 hash is stored;
the raw key is shown to the user exactly once. The non-secret ``prefix`` (first
12 chars) is stored alongside for display and fast narrowing on lookup.
"""

from __future__ import annotations

import hashlib
import secrets

KEY_PREFIX = "rak_"
PREFIX_LEN = 12


def generate_key() -> str:
    """Return a new raw API key (show once, never stored in the clear)."""
    return KEY_PREFIX + secrets.token_urlsafe(30)


def hash_key(raw_key: str) -> str:
    """Return the hex SHA-256 hash of a raw key (what we store/compare)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def key_prefix(raw_key: str) -> str:
    """Return the non-secret display prefix of a raw key."""
    return raw_key[:PREFIX_LEN]


def verify(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw key against a stored hash."""
    return secrets.compare_digest(hash_key(raw_key), stored_hash)
