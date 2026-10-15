"""FastAPI dependencies: database session and the signed-in user.

Sessions are a signed cookie (Starlette ``SessionMiddleware``) carrying only the
user id; the user record is loaded fresh from the database each request.
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.db.base import get_session
from app.db.models import User


class LoginRequired(Exception):
    """Raised by ``require_user`` when no valid session is present."""


def get_db() -> Iterator[Session]:
    """Yield a transactional session, committing on success."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """Return the signed-in user, or ``None`` if not logged in."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = repo.get_user(db, user_id)
    if user is None:
        # Stale cookie (user deleted): clear it.
        request.session.pop("user_id", None)
    return user


def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require a signed-in user; raise ``LoginRequired`` otherwise."""
    if user is None:
        raise LoginRequired()
    return user


def login_redirect(next_url: str = "/") -> RedirectResponse:
    target = f"/login?next={next_url}" if next_url and next_url != "/" else "/login"
    return RedirectResponse(target, status_code=303)
