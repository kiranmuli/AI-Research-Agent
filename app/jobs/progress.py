"""Live progress streaming over Redis pub/sub.

The worker publishes ``{"event": ..., "data": ...}`` messages to a per-job
channel; the web process subscribes and forwards them to the browser as SSE.
Progress is best-effort and live-only — the durable job state always lives in
the database, so a client that connects late can still fetch the final result.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from app.jobs import connection

# How long a completed job's channel sentinel lingers (seconds).
_END_TTL = 60


def progress_channel(job_id: str) -> str:
    return f"job:progress:{job_id}"


def publish(job_id: str, event: str, data) -> None:
    """Publish one progress event for a job (best-effort)."""
    payload = json.dumps({"event": event, "data": data})
    r = connection.get_redis()
    channel = progress_channel(job_id)
    r.publish(channel, payload)
    # Also stash the last event so a late subscriber can detect completion.
    if event in ("done", "error", "end"):
        r.setex(f"{channel}:ended", _END_TTL, event)


def has_ended(job_id: str) -> bool:
    return connection.get_redis().exists(f"{progress_channel(job_id)}:ended") == 1


def subscribe(job_id: str) -> Iterator[dict]:
    """Yield progress events for a job until an ``end`` event arrives.

    Yields dicts of the form ``{"event": str, "data": Any}``.
    """
    r = connection.get_redis()
    channel = progress_channel(job_id)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)
    try:
        # If the job already ended before we subscribed, stop immediately.
        if has_ended(job_id):
            return
        for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            try:
                event = json.loads(message["data"])
            except (ValueError, TypeError):
                continue
            if event.get("event") == "end":
                break
            yield event
    finally:
        try:
            pubsub.close()
        except Exception:  # noqa: BLE001 - closing must never raise to caller
            pass
