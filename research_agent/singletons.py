"""Shared singleton instances — created once, then reused everywhere.

``lru_cache`` makes each factory return the *same* object for the same model, so
the whole app shares one LLM provider and one agent instead of building a new
one per request. The provider (Ollama or a cloud API) is chosen from settings.

All per-run state (loggers, traces, token counts) is passed around locally, so a
single shared agent can safely serve concurrent requests.
"""

from __future__ import annotations

from functools import lru_cache

from app.llm import LLMProvider, get_provider
from research_agent.agent import ResearchAgent


def get_llm(model: str | None = None) -> LLMProvider:
    """Return the shared LLM provider for the given (or default) model."""
    return get_provider(model=model)


@lru_cache(maxsize=8)
def _agent(model: str | None) -> ResearchAgent:
    return ResearchAgent(llm=get_provider(model=model))


def get_agent(model: str | None = None) -> ResearchAgent:
    """Return the shared research agent (reusing the shared LLM provider)."""
    return _agent(model)
