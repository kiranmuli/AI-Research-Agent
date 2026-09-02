"""Gunicorn configuration for the web service.

Uses threaded workers so long-lived SSE streams don't each occupy a full
process. Tune ``WEB_CONCURRENCY`` / ``GUNICORN_THREADS`` for your host.
"""

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('WEB_PORT', '5000')}"
workers = int(os.getenv("WEB_CONCURRENCY", str(min(4, multiprocessing.cpu_count()))))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))

# SSE connections can stay open (and quiet) while the model writes; keep the
# worker timeout comfortably above the max job runtime.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "1800"))
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
# Access logs as structured-ish key=value (real app logs are JSON via structlog).
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sus'
