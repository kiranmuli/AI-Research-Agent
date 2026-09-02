"""WSGI entrypoint for production servers (gunicorn / waitress).

    gunicorn  -c deploy/gunicorn.conf.py  wsgi:app
    waitress-serve --port=5000 wsgi:app
"""

from app.api import create_app

app = create_app()
