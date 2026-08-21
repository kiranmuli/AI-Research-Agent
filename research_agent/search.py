"""Web search via DuckDuckGo (no API key required)."""

from __future__ import annotations

from dataclasses import dataclass

from ddgs import DDGS

import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def web_search(query: str, max_results: int | None = None) -> list[SearchResult]:
    """Return a list of search results for a query."""
    limit = max_results or config.SEARCH_RESULTS
    results: list[SearchResult] = []
    with DDGS() as ddgs:
        for item in ddgs.text(query, max_results=limit):
            url = item.get("href") or item.get("url") or ""
            if not url:
                continue
            results.append(
                SearchResult(
                    title=item.get("title", "").strip() or url,
                    url=url,
                    snippet=item.get("body", "").strip(),
                )
            )
    return results
