"""Chat grounded on a single research report.

The user researches a topic; this service lets them ask follow-up questions
that are answered using *only* the generated report as source material. It
reuses the same pluggable :class:`~app.llm.base.LLMProvider` the agent uses, so
chat runs against Ollama or the cloud API unchanged.
"""

from __future__ import annotations

from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.settings import get_settings

SYSTEM_PROMPT = (
    "You are a research assistant answering questions about ONE research "
    "report. Use only the information in the report below. If the answer is "
    "not contained in the report, say so plainly instead of guessing. Keep "
    "answers concise and, where useful, cite the report's bracketed source "
    "markers like [1], [2].\n\n"
    "=== RESEARCH REPORT ===\n"
    "Topic: {topic}\n\n"
    "{report}\n"
    "=== END OF REPORT ===\n"
)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…[report truncated]"


def build_prompt(
    topic: str,
    report_markdown: str,
    history: list[tuple[str, str]],
    question: str,
    *,
    report_char_limit: int = 24000,
) -> tuple[str, str]:
    """Return ``(system, user)`` prompts for a grounded chat turn.

    ``history`` is a list of ``(role, content)`` tuples in chronological order.
    """
    system = SYSTEM_PROMPT.format(
        topic=topic, report=_truncate(report_markdown, report_char_limit)
    )

    lines: list[str] = []
    if history:
        lines.append("Conversation so far:")
        for role, content in history:
            who = "User" if role == "user" else "Assistant"
            lines.append(f"{who}: {content}")
        lines.append("")
    lines.append(f"User: {question}")
    lines.append("Assistant:")
    return system, "\n".join(lines)


def answer(
    topic: str,
    report_markdown: str,
    history: list[tuple[str, str]],
    question: str,
    *,
    provider: LLMProvider | None = None,
) -> str:
    """Generate a grounded answer to ``question`` about the report."""
    s = get_settings()
    llm = provider or get_provider()
    # Only feed back the most recent turns to keep the prompt bounded.
    recent = history[-(s.chat_history_turns * 2) :] if history else []
    system, user = build_prompt(topic, report_markdown, recent, question)
    return llm.chat(system, user, temperature=0.3).strip()
