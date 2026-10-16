"""Free-form chat assistant: a general conversational helper.

Unlike :mod:`app.services.chat` (which answers only from a research report),
this drives an open-ended, multi-turn conversation and streams the reply.
"""

from __future__ import annotations

from collections.abc import Iterator

from app.llm.base import LLMProvider
from app.llm.factory import get_provider

SYSTEM_PROMPT = (
    "You are a helpful, knowledgeable assistant. Answer clearly and concisely, "
    "use Markdown for structure (headings, lists, code blocks) when it helps, "
    "and say so plainly when you are unsure rather than inventing facts."
)


def stream_reply(
    history: list[tuple[str, str]],
    *,
    provider: LLMProvider | None = None,
) -> Iterator[str]:
    """Stream the assistant's reply given the conversation ``history``.

    ``history`` is ``[(role, content), ...]`` in chronological order, ending
    with the latest user turn.
    """
    llm = provider or get_provider()
    messages = [{"role": role, "content": content} for role, content in history]
    yield from llm.stream_chat(SYSTEM_PROMPT, messages)


def make_title(first_message: str, limit: int = 60) -> str:
    """Derive a short conversation title from the first user message."""
    text = " ".join(first_message.split())
    return text[:limit] + ("…" if len(text) > limit else "") or "New chat"
