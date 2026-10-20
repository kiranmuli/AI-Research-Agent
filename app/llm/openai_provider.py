"""OpenAI backend — talks to the OpenAI API (or any OpenAI-compatible server).

Selected by setting ``LLM_PROVIDER=openai`` with ``OPENAI_API_KEY``. Point it at
a different OpenAI-compatible endpoint (vLLM, LiteLLM, a local gateway, even
Ollama's ``/v1``) by setting ``OPENAI_BASE_URL``.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.llm.base import LLMError, LLMProvider
from app.settings import get_settings


class OpenAIProvider(LLMProvider):
    provider_name = "openai"

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        s = get_settings()
        self.model = model or s.openai_model
        self._api_key = api_key or s.openai_api_key
        self._base_url = base_url or s.openai_base_url
        self._max_tokens = s.openai_max_tokens
        self._client = None  # created lazily so import never requires a key

    def _get_client(self):
        if self._client is None:
            if not self._api_key:
                raise LLMError(
                    "OPENAI_API_KEY is not set; cannot use the OpenAI provider."
                )
            # Imported lazily so the dependency is only needed when selected.
            import openai

            self._client = openai.OpenAI(
                api_key=self._api_key, base_url=self._base_url or None
            )
        return self._client

    def chat_with_tokens(
        self, system: str, user: str, temperature: float = 0.2
    ) -> tuple[str, dict]:
        client = self._get_client()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                max_tokens=self._max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:  # noqa: BLE001 - normalize backend errors
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        text = (resp.choices[0].message.content or "").strip()
        usage = getattr(resp, "usage", None)
        tokens = {
            "prompt": getattr(usage, "prompt_tokens", None) if usage else None,
            "output": getattr(usage, "completion_tokens", None) if usage else None,
        }
        return text, tokens

    def stream_chat(
        self,
        system: str,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> Iterator[str]:
        client = self._get_client()
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)
        try:
            stream = client.chat.completions.create(
                model=self.model,
                max_tokens=self._max_tokens,
                temperature=temperature,
                messages=msgs,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content
                if piece:
                    yield piece
        except Exception as exc:  # noqa: BLE001 - normalize backend errors
            raise LLMError(f"OpenAI stream failed: {exc}") from exc

    def is_available(self) -> tuple[bool, str]:
        if not self._api_key:
            return False, "OPENAI_API_KEY is not set."
        try:
            client = self._get_client()
            client.chat.completions.create(
                model=self.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        except Exception as exc:  # noqa: BLE001 - surface auth/model errors
            return False, f"OpenAI API not usable: {exc}"
        return True, "ok"
