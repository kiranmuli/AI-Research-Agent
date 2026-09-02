"""Local runner for the web app.

For development/convenience: builds the production Flask app (via the factory)
and serves it. In production the app is served by gunicorn (see wsgi.py and
deploy/gunicorn.conf.py), fronted by nginx.

    python web.py

Requires Redis and a database to be reachable, and at least one worker running
(``python -m app.jobs.worker``) to actually process jobs.
"""

from __future__ import annotations

import os

from app.api import create_app
from app.settings import get_settings

app = create_app()


if __name__ == "__main__":
    s = get_settings()
    host = os.getenv("WEB_HOST", s.web_host)
    port = int(os.getenv("WEB_PORT", str(s.web_port)))
    print(f"AI Research Agent -> http://{host}:{port}")

    try:
        # Prefer waitress (a production-grade WSGI server that runs on Windows).
        from waitress import serve

        serve(app, host=host, port=port, threads=16)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)
