"""Authentication routes: sign up, log in, log out (session cookie)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import repository as repo
from app.observability.logging import get_logger
from app.settings import get_settings
from app.webapp.deps import get_db
from app.webapp.security import hash_password, verify_password
from app.webapp.templating import templates

router = APIRouter()
log = get_logger(__name__)

MIN_PASSWORD_LEN = 8


def _safe_next(next_url: str | None) -> str:
    """Only allow same-site relative redirects (prevent open redirect)."""
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if request.session.get("user_id"):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "next": _safe_next(next),
            "allow_signup": get_settings().allow_signup,
            "error": None,
            "user": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = repo.get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "next": _safe_next(next),
                "allow_signup": get_settings().allow_signup,
                "error": "Invalid email or password.",
                "user": None,
            },
            status_code=401,
        )
    repo.touch_user_login(db, user.id)
    request.session["user_id"] = user.id
    log.info("auth.login", user_id=user.id)
    return RedirectResponse(_safe_next(next), status_code=303)


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request, next: str = "/"):
    if not get_settings().allow_signup:
        return RedirectResponse("/login", status_code=303)
    if request.session.get("user_id"):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(
        request,
        "signup.html",
        {"next": _safe_next(next), "error": None, "user": None},
    )


@router.post("/signup", response_class=HTMLResponse)
async def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not settings.allow_signup:
        return RedirectResponse("/login", status_code=303)

    email_norm = email.strip().lower()
    error = None
    if "@" not in email_norm or len(email_norm) < 3:
        error = "Please enter a valid email address."
    elif len(password) < MIN_PASSWORD_LEN:
        error = f"Password must be at least {MIN_PASSWORD_LEN} characters."
    elif repo.get_user_by_email(db, email_norm) is not None:
        error = "An account with that email already exists."

    if error:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {
                "next": _safe_next(next),
                "error": error,
                "user": None,
            },
            status_code=422,
        )

    user = repo.create_user(db, email_norm, hash_password(password))
    request.session["user_id"] = user.id
    log.info("auth.signup", user_id=user.id)
    return RedirectResponse(_safe_next(next), status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse("/login", status_code=303)
