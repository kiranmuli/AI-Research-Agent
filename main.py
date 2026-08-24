"""CLI entry point for the AI Research Agent.

Usage:
    python main.py "your research topic"
    python main.py "your topic" --model llama3.2 --no-save
"""

from __future__ import annotations

import argparse
import sys

import config
from research_agent.report import save_report
from research_agent.singletons import get_agent

# The Windows console uses a limited codepage; the model can emit characters
# (arrows, curly quotes, ...) it cannot encode. Force UTF-8 so printing the
# report never crashes. Saved files are already written as UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Research a topic using a local Ollama model + web search."
    )
    parser.add_argument("topic", help="The topic or question to research.")
    parser.add_argument(
        "--model",
        default=config.OLLAMA_MODEL,
        help=f"Ollama model to use (default: {config.OLLAMA_MODEL}).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Print the report instead of saving it to a file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress logging.",
    )
    args = parser.parse_args()

    agent = get_agent(args.model)
    ok, msg = agent.llm.is_available()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        return 1

    result = agent.research(args.topic, verbose=not args.quiet)

    print("\n" + "=" * 70)
    print(result.report)
    print("=" * 70 + "\n")

    if not args.no_save:
        sources = [(s.title, s.url) for s in result.sources]
        md_path, pdf_path = save_report(result.topic, result.report, sources)
        print(f"Markdown saved to: {md_path}")
        if pdf_path:
            print(f"PDF saved to:      {pdf_path}")
        else:
            print("PDF: could not be generated (Markdown was still saved).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
