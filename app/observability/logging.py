"""Structured logging via structlog.

In production, logs are emitted as one JSON object per line (easy to ship to a
log aggregator). In development they are rendered as readable colored console
lines. Call :func:`configure_logging` once at process startup.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.settings import get_settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    s = get_settings()
    level = getattr(logging, s.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if s.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None):
    """Return a bound structlog logger, configuring on first use."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
