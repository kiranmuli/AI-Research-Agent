"""Production application package for the AI Research Agent.

Layers:
    app.settings        validated configuration (pydantic-settings)
    app.llm             pluggable LLM providers (Ollama, Anthropic)
    app.db              SQLAlchemy models + session management
    app.auth            API-key authentication and tenant scoping
    app.jobs            Redis/RQ background job queue + live progress
    app.observability   structured logging + Prometheus metrics
    app.api             Flask application factory (REST API + web UI)

The domain logic (plan -> search -> read -> synthesize) lives in the
``research_agent`` package and is imported by these layers.
"""

__version__ = "1.0.0"
