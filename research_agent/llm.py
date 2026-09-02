"""Backward-compatible LLM shim.

The real, pluggable providers now live in :mod:`app.llm`. This module keeps the
old import path working: ``from research_agent.llm import LLM`` returns an
instance of the configured provider (Ollama by default).

Prefer ``from app.llm import get_provider, LLMProvider`` in new code.
"""

from __future__ import annotations

from app.llm import LLMProvider
from app.llm.factory import build_provider


def LLM(model: str | None = None, host: str | None = None) -> LLMProvider:  # noqa: N802
    """Construct the configured LLM provider (kept as a callable for compat).

    ``host`` is honoured only by the Ollama provider and ignored otherwise.
    """
    from app.settings import get_settings

    s = get_settings()
    if s.llm_provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider

        return OllamaProvider(model=model, host=host)
    return build_provider(model=model)


__all__ = ["LLM", "LLMProvider"]
