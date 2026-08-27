"""Thin wrapper around a local Ollama model."""

from __future__ import annotations

import ollama

import config


def _field(resp, name: str):
    """Read a field from an Ollama response (dict or pydantic object)."""
    if isinstance(resp, dict):
        return resp.get(name)
    return getattr(resp, name, None)


class LLM:
    """Talks to a local Ollama server."""

    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or config.OLLAMA_MODEL
        self._client = ollama.Client(host=host or config.OLLAMA_HOST)

    def chat(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Send a system + user prompt and return the assistant text."""
        text, _ = self.chat_with_tokens(system, user, temperature)
        return text

    def chat_with_tokens(
        self, system: str, user: str, temperature: float = 0.2
    ) -> tuple[str, dict]:
        """Like chat(), but also returns token counts for this call.

        Tokens are returned (not stored on the instance) so a single shared LLM
        can be used concurrently without runs clobbering each other's counts.
        """
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": temperature},
        )
        tokens = {
            "prompt": _field(response, "prompt_eval_count"),
            "output": _field(response, "eval_count"),
        }
        return response["message"]["content"].strip(), tokens

    def is_available(self) -> tuple[bool, str]:
        """Check the Ollama server is reachable and the model is present."""
        try:
            listed = self._client.list()
        except Exception as exc:  # noqa: BLE001 - surface any connection issue
            return False, f"Cannot reach Ollama at {config.OLLAMA_HOST}: {exc}"

        names = {m.get("model", m.get("name", "")) for m in listed.get("models", [])}
        # Match either the exact tag or the base name (e.g. "llama3.2").
        if self.model in names or any(n.split(":")[0] == self.model for n in names):
            return True, "ok"
        return (
            False,
            f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}",
        )
