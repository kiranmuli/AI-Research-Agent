"""Background job queue (Redis + RQ) and live progress streaming.

The web process enqueues a research job and returns immediately. A separate
worker process runs the agent, persists the result, and publishes progress
lines to a Redis channel that the web process streams to the browser (SSE).
"""

from app.jobs.connection import get_queue, get_redis
from app.jobs.progress import progress_channel, publish, subscribe

__all__ = [
    "get_queue",
    "get_redis",
    "progress_channel",
    "publish",
    "subscribe",
]
