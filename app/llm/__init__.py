"""Pluggable LLM providers.

The rest of the app depends only on the :class:`LLMProvider` interface, so the
concrete backend (local Ollama or the Anthropic cloud API) is chosen at runtime
from configuration via :func:`get_provider`.
"""

from app.llm.base import LLMProvider
from app.llm.factory import get_provider

__all__ = ["LLMProvider", "get_provider"]
