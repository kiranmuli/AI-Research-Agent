"""Ollama backend — talks to a local or self-hosted Ollama server."""

from __future__ import annotations

import ollama

from app.llm.base import LLMError, LLMProvider
from app.settings import get_settings


def _field(resp, name: str):
    """Read a field from an Ollama response (dict or pydantic object)."""
    if isinstance(resp, dict):
        return resp.get(name)
    return getattr(resp, name, None)


class OllamaProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None):
        s = get_settings()
        self.model = model or s.ollama_model
        self._host = host or s.ollama_host
        self._client = ollama.Client(host=self._host)

    def chat_with_tokens(
        self, system: str, user: str, temperature: float = 0.2
    ) -> tuple[str, dict]:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                options={"temperature": temperature},
            )
        except Exception as exc:  # noqa: BLE001 - normalize backend errors
            raise LLMError(f"Ollama chat failed: {exc}") from exc

        tokens = {
            "prompt": _field(response, "prompt_eval_count"),
            "output": _field(response, "eval_count"),
        }
        return response["message"]["content"].strip(), tokens

    def is_available(self) -> tuple[bool, str]:
        try:
            listed = self._client.list()
        except Exception as exc:  # noqa: BLE001 - surface any connection issue
            return False, f"Cannot reach Ollama at {self._host}: {exc}"

        names = {m.get("model", m.get("name", "")) for m in listed.get("models", [])}
        if self.model in names or any(n.split(":")[0] == self.model for n in names):
            return True, "ok"
        return (
            False,
            f"Model '{self.model}' not found. Pull it with: ollama pull {self.model}",
        )
