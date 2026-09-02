"""RQ worker entrypoint.

Run with:  ``python -m app.jobs.worker``  (or the ``rq worker`` CLI).
Each worker process consumes research jobs from the queue and executes them.
"""

from __future__ import annotations

from rq import Worker

from app.jobs.connection import QUEUE_NAME, get_redis
from app.observability.logging import configure_logging, get_logger


def main() -> None:
    configure_logging()
    log = get_logger(__name__)
    log.info("worker.starting", queue=QUEUE_NAME)
    worker = Worker([QUEUE_NAME], connection=get_redis())
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
