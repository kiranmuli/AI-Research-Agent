"""The provider-agnostic LLM interface the agent depends on.

Any backend (Ollama, Anthropic, ...) implements this small surface. Keeping it
narrow is what lets the same :class:`~research_agent.agent.ResearchAgent` run
unchanged against a local model or a hosted API.
"""

from __future__ import annotations

import abc


class LLMProvider(abc.ABC):
    """Minimal chat interface shared by every backend."""

    #: Human-readable model identifier (used in traces, reports, logs).
    model: str

    #: Short provider name, e.g. "ollama" or "anthropic".
    provider_name: str

    @abc.abstractmethod
    def chat_with_tokens(
        self, system: str, user: str, temperature: float = 0.2
    ) -> tuple[str, dict]:
        """Send a system + user prompt.

        Returns ``(text, tokens)`` where ``tokens`` is
        ``{"prompt": int | None, "output": int | None}``. Tokens are returned
        (not stored on the instance) so one shared provider can serve concurrent
        requests without runs clobbering each other's counts.
        """

    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Convenience wrapper returning only the assistant text."""
        text, _ = self.chat_with_tokens(system, user, temperature)
        return text

    @abc.abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """Check the backend is reachable and the model is usable.

        Returns ``(ok, message)``. ``message`` is "ok" on success or a
        human-readable, actionable error otherwise.
        """


class LLMError(RuntimeError):
    """Raised when an LLM backend fails in a way callers should surface."""
