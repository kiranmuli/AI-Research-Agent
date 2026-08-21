"""Research orchestration: plan -> search -> read -> synthesize."""

from __future__ import annotations

from dataclasses import dataclass, field

import config
from research_agent.fetch import fetch_text
from research_agent.llm import LLM
from research_agent.search import SearchResult, web_search


@dataclass
class Source:
    title: str
    url: str
    text: str


@dataclass
class ResearchResult:
    topic: str
    subquestions: list[str]
    report: str
    sources: list[Source] = field(default_factory=list)


PLANNER_SYSTEM = (
    "You are a research planner. Given a topic, produce a short list of focused "
    "search queries that together would let someone research the topic well. "
    "Return ONLY the queries, one per line, with no numbering or extra text."
)

SYNTHESIS_SYSTEM = (
    "You are a meticulous research analyst. Using ONLY the provided sources, write "
    "a clear, well-structured report on the topic in Markdown. Use headings and "
    "bullet points where helpful. Cite sources inline as [n] matching the source "
    "numbers given. Be objective, note disagreements between sources, and do not "
    "invent facts that are not supported by the sources."
)


class ResearchAgent:
    def __init__(self, llm: LLM | None = None, verbose: bool = True):
        self.llm = llm or LLM()
        self.verbose = verbose

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def plan(self, topic: str) -> list[str]:
        """Ask the LLM for a handful of focused search queries."""
        raw = self.llm.chat(
            system=PLANNER_SYSTEM,
            user=f"Topic: {topic}\n\nGive {config.NUM_SUBQUESTIONS} search queries.",
        )
        queries = [q.strip("-* \t") for q in raw.splitlines() if q.strip()]
        queries = [q for q in queries if q][: config.NUM_SUBQUESTIONS]
        # Always include the raw topic as a fallback query.
        if topic not in queries:
            queries.insert(0, topic)
        return queries

    def gather(self, queries: list[str]) -> list[Source]:
        """Run searches, then fetch and read up to MAX_SOURCES unique pages."""
        seen: set[str] = set()
        candidates: list[SearchResult] = []
        for q in queries:
            self._log(f"  searching: {q}")
            for res in web_search(q):
                if res.url not in seen:
                    seen.add(res.url)
                    candidates.append(res)

        sources: list[Source] = []
        for res in candidates:
            if len(sources) >= config.MAX_SOURCES:
                break
            self._log(f"  reading: {res.url}")
            text = fetch_text(res.url)
            if text:
                sources.append(Source(title=res.title, url=res.url, text=text))
        return sources

    def synthesize(self, topic: str, sources: list[Source]) -> str:
        """Combine sources into a cited report."""
        if not sources:
            return (
                "No readable sources were retrieved for this topic. "
                "Try a different query or check your internet connection."
            )

        blocks = []
        for i, s in enumerate(sources, 1):
            blocks.append(f"[{i}] {s.title} ({s.url})\n{s.text}")
        corpus = "\n\n---\n\n".join(blocks)

        user = (
            f"Topic: {topic}\n\n"
            f"Sources:\n\n{corpus}\n\n"
            "Write the research report now."
        )
        return self.llm.chat(system=SYNTHESIS_SYSTEM, user=user, temperature=0.3)

    def research(self, topic: str) -> ResearchResult:
        self._log("Planning search queries...")
        queries = self.plan(topic)
        self._log(f"Queries: {queries}")

        self._log("Gathering sources...")
        sources = self.gather(queries)
        self._log(f"Collected {len(sources)} readable source(s).")

        self._log("Synthesizing report...")
        report = self.synthesize(topic, sources)

        return ResearchResult(
            topic=topic,
            subquestions=queries,
            report=report,
            sources=sources,
        )
