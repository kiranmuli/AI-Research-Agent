"""ASGI entrypoint for the FastAPI web app (served by uvicorn).

    uvicorn asgi:app --host 0.0.0.0 --port 5000
"""

from app.webapp import create_app

app = create_app()
