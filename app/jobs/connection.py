"""Redis connection and RQ queue singletons."""

from __future__ import annotations

from functools import lru_cache

import redis
from rq import Queue

from app.settings import get_settings

QUEUE_NAME = "research"


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    s = get_settings()
    # decode_responses=False: RQ needs raw bytes on its own connection. We wrap
    # pub/sub payloads as UTF-8 ourselves where needed.
    return redis.Redis.from_url(s.redis_url)


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    s = get_settings()
    return Queue(
        QUEUE_NAME,
        connection=get_redis(),
        default_timeout=s.job_timeout,
    )
