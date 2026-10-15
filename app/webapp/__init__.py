"""Browser-facing FastAPI application: user login, research, history, chat.

The app factory :func:`create_app` wires routers, session middleware, static
files, and the Prometheus metrics endpoint. It reuses the existing engine
(``research_agent``), persistence (``app.db``), queue (``app.jobs``), and LLM
providers (``app.llm``) unchanged.
"""

from app.webapp.main import create_app

__all__ = ["create_app"]
