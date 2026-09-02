"""Flask application factory (REST API + browser UI)."""

from app.api.app import create_app

__all__ = ["create_app"]
