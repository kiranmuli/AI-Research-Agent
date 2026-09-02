#!/usr/bin/env sh
# Container entrypoint. Roles are selected by the first argument:
#   web     -> run DB migrations, then serve the API/UI via gunicorn
#   worker  -> run an RQ worker consuming research jobs
#   migrate -> run DB migrations and exit
set -eu

ROLE="${1:-web}"

wait_for_db() {
  echo "waiting for database..."
  python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.settings import get_settings
url = get_settings().database_url
for attempt in range(60):
    try:
        create_engine(url).connect().execute(text("SELECT 1"))
        print("database is up")
        sys.exit(0)
    except Exception as exc:
        print(f"  db not ready ({attempt+1}/60): {exc}")
        time.sleep(2)
sys.exit("database did not become ready in time")
PY
}

case "$ROLE" in
  web)
    wait_for_db
    echo "running migrations..."
    alembic upgrade head
    echo "starting web server..."
    exec gunicorn -c deploy/gunicorn.conf.py wsgi:app
    ;;
  worker)
    wait_for_db
    echo "starting rq worker..."
    exec python -m app.jobs.worker
    ;;
  migrate)
    wait_for_db
    exec alembic upgrade head
    ;;
  *)
    echo "unknown role: $ROLE (expected web|worker|migrate)" >&2
    exit 1
    ;;
esac
