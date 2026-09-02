"""Validated, environment-driven configuration.

Everything is read from environment variables (or a local ``.env`` file) and
validated once at import time. Access the singleton via ``get_settings()``.

The legacy flat ``config`` module re-exports these values so existing imports
(``import config; config.OLLAMA_MODEL``) keep working unchanged.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["ollama", "anthropic"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- runtime ---
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str = Field(
        default="dev-insecure-change-me",
        description="Flask secret / signing key. MUST be overridden in production.",
    )

    # --- LLM provider selection ---
    llm_provider: LLMProviderName = "ollama"

    # Ollama (local / self-hosted)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Anthropic (cloud API)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    anthropic_max_tokens: int = 4096

    # --- research behaviour ---
    search_results: int = Field(5, alias="research_search_results")
    num_subquestions: int = Field(3, alias="research_subquestions")
    max_sources: int = Field(6, alias="research_max_sources")
    max_source_chars: int = Field(6000, alias="research_max_source_chars")

    # --- networking ---
    http_timeout: int = Field(20, alias="research_http_timeout")
    user_agent: str = Field(
        "AI-Research-Agent/1.0 (+https://github.com/kiranmuli/AI-Research-Agent)",
        alias="research_user_agent",
    )

    # --- output ---
    reports_dir: str = Field("reports", alias="research_reports_dir")
    traces_dir: str = Field("traces", alias="research_traces_dir")

    # --- persistence ---
    database_url: str = "postgresql+psycopg://research:research@localhost:5432/research"

    # --- queue / cache ---
    redis_url: str = "redis://localhost:6379/0"
    job_timeout: int = 900  # seconds a single research job may run
    job_result_ttl: int = 86400  # keep finished job metadata this long

    # --- web / API ---
    web_host: str = "127.0.0.1"
    web_port: int = 5000
    rate_limit_default: str = "60/minute"
    rate_limit_research: str = "10/minute"
    cors_origins: str = ""  # comma-separated; empty = same-origin only

    # --- auth ---
    # When true, the REST API requires a valid API key. The browser UI is
    # always reachable (it is meant for humans behind your own network/proxy).
    require_api_key: bool = True

    # --- observability ---
    log_level: str = "INFO"
    log_json: bool = True
    metrics_enabled: bool = True

    @model_validator(mode="after")
    def _check_provider_config(self) -> Settings:
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            # Do not hard-fail at import (tests / tooling import settings without
            # a key). Availability is checked at request time by the provider.
            pass
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def active_model(self) -> str:
        """The model name for the currently selected provider."""
        return (
            self.anthropic_model
            if self.llm_provider == "anthropic"
            else self.ollama_model
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
