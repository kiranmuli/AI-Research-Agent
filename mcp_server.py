"""MCP server exposing the AI Research Agent as tools for Claude.

Run directly (``python mcp_server.py``) to start a stdio MCP server. Add it to
Claude Desktop / Claude Code config so Claude can call these tools.

Note: this server communicates with Claude over stdout, so the underlying agent
is run silently (verbose=False) — printing progress would corrupt the protocol.
"""

from __future__ import annotations

from mcp.server import MCPServer

from research_agent.search import web_search as _web_search
from research_agent.singletons import get_agent

mcp = MCPServer("ai-research-agent")


@mcp.tool()
def research(topic: str) -> str:
    """Research a topic on the web and return a cited Markdown report.

    Uses a local Ollama model to plan search queries, searches the web,
    reads the top pages, and synthesizes a report. Requires Ollama running
    locally. Best for questions that need up-to-date or sourced information.

    Args:
        topic: The topic or question to research.
    """
    agent = get_agent()
    ok, msg = agent.llm.is_available()
    if not ok:
        return f"Research agent unavailable: {msg}"

    result = agent.research(topic, verbose=False)

    lines = [result.report, "", "## Sources", ""]
    if result.sources:
        for i, s in enumerate(result.sources, 1):
            lines.append(f"{i}. [{s.title}]({s.url})")
    else:
        lines.append("_No sources retrieved._")
    return "\n".join(lines)


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return the top results (title, URL, snippet).

    A fast lookup that does NOT read pages or use the LLM. Use this when you
    just need links/snippets rather than a full synthesized report.

    Args:
        query: The search query.
        max_results: How many results to return (default 5).
    """
    results = _web_search(query, max_results=max_results)
    if not results:
        return "No results found."
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}")
    return "\n\n".join(lines)


if __name__ == "__main__":
    mcp.run()
