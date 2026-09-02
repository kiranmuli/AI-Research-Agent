"""Lightweight local observability for a research run.

Each run builds a RunTrace that records per-step timings, token usage, and a few
metrics, then can be saved as a JSON file under ``traces/``. No cloud, no keys —
everything stays on your machine.
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime

import config


class RunTrace:
    def __init__(self, topic: str, model: str):
        self.topic = topic
        self.model = model
        self.started = datetime.now()
        self._t0 = time.perf_counter()
        self.steps: list[dict] = []
        self.metrics: dict = {}
        self.tokens = {"prompt": 0, "output": 0}
        self.sources: list[dict] = []
        self.error: str | None = None

    @contextmanager
    def step(self, name: str):
        """Time a step; records its duration even if it raises."""
        start = time.perf_counter()
        try:
            yield
        finally:
            self.steps.append(
                {"name": name, "seconds": round(time.perf_counter() - start, 2)}
            )

    def add_tokens(self, prompt: int | None, output: int | None) -> None:
        if prompt:
            self.tokens["prompt"] += prompt
        if output:
            self.tokens["output"] += output

    def metric(self, key: str, value) -> None:
        self.metrics[key] = value

    def summary(self) -> dict:
        return {
            "topic": self.topic,
            "model": self.model,
            "started_at": self.started.isoformat(timespec="seconds"),
            "total_seconds": round(time.perf_counter() - self._t0, 2),
            "steps": self.steps,
            "metrics": {**self.metrics, "tokens": self.tokens},
            "sources": self.sources,
            "error": self.error,
        }


def _slug(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]) or "run"


def save_trace(summary: dict) -> str:
    """Write a trace summary to traces/<timestamp>-<slug>.json; return the path."""
    os.makedirs(config.TRACES_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{_slug(summary.get('topic', ''))}.json"
    path = os.path.join(config.TRACES_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return path


def format_summary(summary: dict) -> str:
    """A compact, human-readable one-block summary for the terminal."""
    m = summary.get("metrics", {})
    tok = m.get("tokens", {})
    lines = [
        "observability ------------------------------------------",
        f"  model         : {summary.get('model')}",
        f"  total time    : {summary.get('total_seconds')}s",
    ]
    for s in summary.get("steps", []):
        lines.append(f"  step {s['name']:<7}: {s['seconds']}s")
    lines.append(
        f"  queries={m.get('num_queries', 0)}  "
        f"links={m.get('candidate_links', 0)}  "
        f"read={m.get('sources_read', 0)}  "
        f"report_chars={m.get('report_chars', 0)}"
    )
    lines.append(
        f"  tokens        : prompt={tok.get('prompt', 0)} "
        f"output={tok.get('output', 0)}"
    )
    lines.append("--------------------------------------------------------")
    return "\n".join(lines)
