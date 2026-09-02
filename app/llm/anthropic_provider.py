"""Anthropic backend — talks to the hosted Claude API.

Selected in production by setting ``LLM_PROVIDER=anthropic`` and providing
``ANTHROPIC_API_KEY``. The model defaults to ``ANTHROPIC_MODEL``.
"""

from __future__ import annotations

from app.llm.base import LLMError, LLMProvider
from app.settings import get_settings


class AnthropicProvider(LLMProvider):
    provider_name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        s = get_settings()
        self.model = model or s.anthropic_model
        self._api_key = api_key or s.anthropic_api_key
        self._max_tokens = s.anthropic_max_tokens
        self._client = None  # created lazily so import never requires a key

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise LLMError(
                    "ANTHROPIC_API_KEY is not set; cannot use the Anthropic provider."
                )
            # Imported lazily so the dependency is only needed when this
            # provider is actually selected.
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat_with_tokens(
        self, system: str, user: str, temperature: float = 0.2
    ) -> tuple[str, dict]:
        client = self._get_client()
        try:
            resp = client.messages.create(
                model=self.model,
                max_tokens=self._max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # noqa: BLE001 - normalize backend errors
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        ).strip()
        usage = getattr(resp, "usage", None)
        tokens = {
            "prompt": getattr(usage, "input_tokens", None) if usage else None,
            "output": getattr(usage, "output_tokens", None) if usage else None,
        }
        return text, tokens

    def is_available(self) -> tuple[bool, str]:
        if not self._api_key:
            return False, "ANTHROPIC_API_KEY is not set."
        try:
            client = self._get_client()
            # A cheap 1-token round-trip verifies the key and model exist.
            client.messages.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        except Exception as exc:  # noqa: BLE001 - surface auth/model errors
            return False, f"Anthropic API not usable: {exc}"
        return True, "ok"
