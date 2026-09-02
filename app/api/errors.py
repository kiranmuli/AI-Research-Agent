"""JSON error handling for the API."""

from __future__ import annotations

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.observability.logging import get_logger

log = get_logger(__name__)


class ApiError(Exception):
    """Raise to return a JSON error with a specific status code."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(err: ApiError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(HTTPException)
    def _handle_http_error(err: HTTPException):
        # Keep JSON for API routes; let others use the default page.
        if request.path.startswith("/api") or request.path in ("/healthz", "/readyz"):
            return jsonify(error=err.description), err.code
        return err

    @app.errorhandler(Exception)
    def _handle_unexpected(err: Exception):
        log.error("unhandled_exception", error=str(err), path=request.path)
        if request.path.startswith("/api"):
            return jsonify(error="Internal server error"), 500
        raise err
