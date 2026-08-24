"""Shared singleton instances — created once, then reused everywhere.

`lru_cache` makes each factory return the *same* object for the same model, so
the whole app shares one Ollama connection and one agent instead of building a
new one for every request.

The public helpers normalise ``None`` to the configured default model first, so
``get_llm()``, ``get_llm(None)`` and ``get_llm("<default>")`` all resolve to the
one same instance (calling the cache with different argument shapes would
otherwise create separate copies).
"""

from __future__ import annotations

from functools import lru_cache

import config
from research_agent.agent import ResearchAgent
from research_agent.llm import LLM


@lru_cache(maxsize=4)
def _llm(model: str) -> LLM:
    return LLM(model=model)


@lru_cache(maxsize=4)
def _agent(model: str) -> ResearchAgent:
    return ResearchAgent(llm=_llm(model))


def get_llm(model: str | None = None) -> LLM:
    """Return the shared LLM (Ollama) client for the given (or default) model."""
    return _llm(model or config.OLLAMA_MODEL)


def get_agent(model: str | None = None) -> ResearchAgent:
    """Return the shared research agent (reusing the shared LLM)."""
    return _agent(model or config.OLLAMA_MODEL)
