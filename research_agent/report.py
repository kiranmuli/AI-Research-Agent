"""Write research results to a Markdown report file."""

from __future__ import annotations

import os
import re
from datetime import datetime

import config


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "report"


def save_report(topic: str, body: str, sources: list[tuple[str, str]]) -> str:
    """Write the report to reports/<timestamp>-<slug>.md and return its path."""
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(config.REPORTS_DIR, f"{stamp}-{_slugify(topic)}.md")

    lines = [
        f"# Research Report: {topic}",
        "",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"— model: {config.OLLAMA_MODEL}*",
        "",
        body.strip(),
        "",
        "## Sources",
        "",
    ]
    if sources:
        for i, (title, url) in enumerate(sources, 1):
            lines.append(f"{i}. [{title}]({url})")
    else:
        lines.append("_No sources retrieved._")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return path
