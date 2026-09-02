"""Prometheus metrics.

Exposes counters/histograms updated across the app and a helper that renders
the metrics exposition format for the ``/metrics`` endpoint.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# --- HTTP ---
HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency.",
    ["method", "endpoint"],
)

# --- Jobs ---
JOBS_TOTAL = Counter(
    "research_jobs_total",
    "Research jobs by terminal status.",
    ["status"],
)
JOB_DURATION = Histogram(
    "research_job_duration_seconds",
    "End-to-end research job duration.",
    buckets=(1, 5, 10, 20, 30, 60, 120, 300, 600),
)


def metrics_response() -> tuple[bytes, str]:
    """Return ``(body, content_type)`` for the metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
