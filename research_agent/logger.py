"""Simple, readable step logging for the research agent.

Logs go to stderr so they never mix with the report (stdout) or interfere with
the MCP server's protocol channel. ASCII-only so it renders on any terminal.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime


class StepLogger:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._run_start: float | None = None
        self._step_start: float | None = None

    # -- internal ---------------------------------------------------------
    def _w(self, line: str = "") -> None:
        if self.enabled:
            print(line, file=sys.stderr, flush=True)

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%H:%M:%S")

    # -- lifecycle --------------------------------------------------------
    def start(self, topic: str) -> None:
        self._run_start = time.perf_counter()
        self._w()
        self._w("=" * 64)
        self._w(f" AI RESEARCH AGENT  |  topic: {topic}")
        self._w(f" started at {self._now()}")
        self._w("=" * 64)

    def step(self, number: int, total: int, name: str, detail: str = "") -> None:
        self._step_start = time.perf_counter()
        self._w()
        self._w(f"[STEP {number}/{total}] {name}")
        if detail:
            self._w(f"          {detail}")
        self._w("-" * 64)

    def step_done(self, summary: str = "") -> None:
        took = ""
        if self._step_start is not None:
            took = f" ({time.perf_counter() - self._step_start:.1f}s)"
        self._w(f"   done{took}. {summary}".rstrip())

    def finish(self) -> None:
        total = ""
        if self._run_start is not None:
            total = f" in {time.perf_counter() - self._run_start:.1f}s"
        self._w()
        self._w("=" * 64)
        self._w(f" FINISHED{total} at {self._now()}")
        self._w("=" * 64)
        self._w()

    # -- line-level markers ----------------------------------------------
    def info(self, msg: str) -> None:
        self._w(f"   {msg}")

    def ok(self, msg: str) -> None:
        self._w(f"   [ok]   {msg}")

    def skip(self, msg: str) -> None:
        self._w(f"   [skip] {msg}")

    def wait(self, msg: str) -> None:
        self._w(f"   [..]   {msg}")
