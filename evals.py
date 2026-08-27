"""A tiny eval harness for the research agent.

Runs the agent on a set of test topics and auto-checks each report against a
few quality signals, then prints a scoreboard and saves the results. Use it to
compare models or prompt changes with numbers instead of eyeballing PDFs.

Run:
    python evals.py                 # run the built-in test cases
    python evals.py --topic "..."   # run one ad-hoc topic
    python evals.py --model llama3.2 --cases my_cases.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime

import config
from research_agent.singletons import get_agent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

RESULTS_DIR = os.getenv("RESEARCH_EVAL_DIR", "eval_results")

# Each case: a topic plus words the report must mention to be "on topic".
DEFAULT_CASES = [
    {"topic": "benefits of green tea", "must_include": ["green tea"]},
    {"topic": "how does solar power work", "must_include": ["solar"]},
    {"topic": "iPhone vs Samsung — which is better?",
     "must_include": ["iphone", "samsung"]},
]


def evaluate(must_include: list[str], report: str, trace: dict) -> dict[str, bool]:
    """Return a dict of check-name -> pass/fail for one run.

    `on_topic` is only included when there are terms to check, so ad-hoc topics
    (no must_include) don't get a vacuous free pass inflating the score.
    """
    metrics = (trace or {}).get("metrics", {})
    low = report.lower()
    checks = {
        "no_error": not (trace or {}).get("error"),
        "has_report": len(report) >= 300,
        "read_2plus": metrics.get("sources_read", 0) >= 2,
        "cites_sources": bool(re.search(r"\[\d+\]", report)),
    }
    if must_include:
        checks["on_topic"] = all(term.lower() in low for term in must_include)
    return checks


def run_cases(cases: list[dict], model: str | None = None) -> dict:
    agent = get_agent(model)
    ok, msg = agent.llm.is_available()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        return {}

    rows = []
    for i, case in enumerate(cases, 1):
        topic = case["topic"]
        must = case.get("must_include", [])
        print(f"[{i}/{len(cases)}] researching: {topic} ...", flush=True)
        result = agent.research(topic, verbose=False)
        checks = evaluate(must, result.report or "", result.trace or {})
        metrics = (result.trace or {}).get("metrics", {})
        tokens = metrics.get("tokens", {})
        rows.append(
            {
                "topic": topic,
                "checks": checks,
                "passed": sum(checks.values()),
                "total": len(checks),
                "seconds": (result.trace or {}).get("total_seconds"),
                "sources_read": metrics.get("sources_read", 0),
                "report_chars": metrics.get("report_chars", 0),
                "tokens_out": tokens.get("output", 0),
            }
        )

    return {
        "model": agent.llm.model,
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
    }


def print_scoreboard(summary: dict) -> None:
    rows = summary.get("rows", [])
    if not rows:
        return
    # Rows may carry different check sets (e.g. on_topic is optional).
    check_names = sorted({name for r in rows for name in r["checks"]})

    print("\n" + "=" * 72)
    print(f"EVAL SCOREBOARD  |  model: {summary.get('model')}")
    print("=" * 72)
    header = f"{'topic':<34}{'score':>7}{'time':>8}{'read':>6}{'tok_out':>9}"
    print(header)
    print("-" * 72)
    total_passed = total_checks = 0
    for r in rows:
        total_passed += r["passed"]
        total_checks += r["total"]
        topic = (r["topic"][:31] + "...") if len(r["topic"]) > 34 else r["topic"]
        secs = f"{r['seconds']}s" if r["seconds"] is not None else "-"
        print(
            f"{topic:<34}{r['passed']}/{r['total']:>5}{secs:>8}"
            f"{r['sources_read']:>6}{r['tokens_out']:>9}"
        )
    print("-" * 72)
    pct = (100 * total_passed / total_checks) if total_checks else 0
    print(f"overall checks passed: {total_passed}/{total_checks}  ({pct:.0f}%)")
    print("checks:", ", ".join(check_names))
    print("=" * 72 + "\n")


def save_results(summary: dict) -> str:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(RESULTS_DIR, f"eval-{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the research agent.")
    parser.add_argument("--model", default=None, help="Ollama model to test.")
    parser.add_argument("--topic", default=None, help="Run one ad-hoc topic.")
    parser.add_argument("--cases", default=None, help="JSON file of test cases.")
    args = parser.parse_args()

    if args.topic:
        cases = [{"topic": args.topic, "must_include": []}]
    elif args.cases:
        with open(args.cases, encoding="utf-8") as fh:
            cases = json.load(fh)
    else:
        cases = DEFAULT_CASES

    summary = run_cases(cases, args.model)
    if not summary:
        return 1
    print_scoreboard(summary)
    path = save_results(summary)
    print(f"Results saved to: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
