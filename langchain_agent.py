"""LangChain version of the research agent — for comparison.

The hand-built agent (``research_agent/agent.py``) runs a FIXED pipeline that we
coded by hand: plan -> search -> read -> write, always in that order.

This version is a self-deciding agent instead. We just hand LangChain two tools
(search the web, read a page) and a goal; the model itself decides when to
search, which pages to read, and when it has enough to write the report. That
"think -> act -> observe -> repeat" loop is what a framework gives you for free.

Run:  python langchain_agent.py "your topic"
"""

from __future__ import annotations

import sys
import warnings

warnings.filterwarnings("ignore", message=".*create_react_agent has been moved.*")

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from research_agent.fetch import fetch_text as _fetch_text
from research_agent.report import save_report
from research_agent.search import web_search as _web_search

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# --- Tools the model is allowed to use --------------------------------------
@tool
def search_web(query: str) -> str:
    """Search the web for a query and return top results as
    'title | url | snippet' lines."""
    results = _web_search(query, max_results=config.SEARCH_RESULTS)
    if not results:
        return "No results found."
    return "\n".join(f"{r.title} | {r.url} | {r.snippet}" for r in results)


@tool
def read_url(url: str) -> str:
    """Fetch a web page and return its readable text (truncated)."""
    return _fetch_text(url) or f"Could not read {url}."


SYSTEM = (
    "You are a research assistant. To research the user's topic: first use "
    "search_web to find sources, then use read_url to read at least two of the "
    "most relevant pages before answering. Finally, write a clear, "
    "well-structured report in Markdown. Do NOT add your own Sources section — "
    "a list of the pages you read is appended automatically. Never invent facts."
)


def build_agent(model: str | None = None):
    llm = ChatOllama(
        model=model or config.OLLAMA_MODEL,
        base_url=config.OLLAMA_HOST,
        temperature=0.2,
    )
    return create_react_agent(llm, tools=[search_web, read_url], prompt=SYSTEM)


def research(topic: str, model: str | None = None, verbose: bool = True):
    """Run the LangChain agent; return (report_text, sources)."""
    agent = build_agent(model)

    def log(msg: str) -> None:
        if verbose:
            print(msg, file=sys.stderr, flush=True)

    log(f"[langchain agent] researching: {topic}\n")
    report = ""
    read_pages: list[tuple[str, str]] = []

    for step in agent.stream(
        {"messages": [HumanMessage(content=topic)]},
        stream_mode="values",
        config={"recursion_limit": 15},
    ):
        last = step["messages"][-1]
        kind = last.__class__.__name__
        if kind == "AIMessage":
            calls = getattr(last, "tool_calls", None) or []
            if calls:
                for tc in calls:
                    args = ", ".join(str(v) for v in tc["args"].values())
                    log(f"  [decides] call {tc['name']}({args})")
                    if tc["name"] == "read_url":
                        url = tc["args"].get("url", "")
                        if url and url not in [u for _, u in read_pages]:
                            read_pages.append((url, url))
            elif last.content:
                report = last.content
        elif kind == "ToolMessage":
            log(f"  [result]  {last.name} -> {len(last.content)} chars")

    log("\n[langchain agent] done.\n")
    return report, read_pages


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python langchain_agent.py "your topic"', file=sys.stderr)
        return 1
    topic = sys.argv[1]

    report, sources = research(topic)

    print("\n" + "=" * 70)
    print(report)
    print("=" * 70 + "\n")

    md_path, pdf_path = save_report(topic, report, sources)
    print(f"Markdown saved to: {md_path}")
    if pdf_path:
        print(f"PDF saved to:      {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
