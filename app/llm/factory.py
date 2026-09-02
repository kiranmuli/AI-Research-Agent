"""Select and build the configured LLM provider."""

from __future__ import annotations

from functools import lru_cache

from app.llm.base import LLMProvider
from app.settings import get_settings


def build_provider(
    provider: str | None = None, model: str | None = None
) -> LLMProvider:
    """Construct a provider instance (not cached).

    ``provider`` defaults to ``LLM_PROVIDER`` from settings; ``model`` overrides
    that provider's default model.
    """
    s = get_settings()
    name = (provider or s.llm_provider).lower()

    if name == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(model=model)
    if name == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{name}'. Expected one of: ollama, anthropic."
    )


@lru_cache(maxsize=8)
def _cached(provider: str, model: str) -> LLMProvider:
    return build_provider(provider, model)


def get_provider(
    provider: str | None = None, model: str | None = None
) -> LLMProvider:
    """Return a shared provider instance for the given provider/model.

    Normalizes ``None`` to the configured defaults first so all callers resolve
    to the same cached instance.
    """
    s = get_settings()
    name = (provider or s.llm_provider).lower()
    resolved_model = model or (
        s.anthropic_model if name == "anthropic" else s.ollama_model
    )
    return _cached(name, resolved_model)
