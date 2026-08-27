"""Research orchestration: plan -> search -> read -> synthesize."""

from __future__ import annotations

from dataclasses import dataclass, field

import config
from research_agent.fetch import fetch_text
from research_agent.llm import LLM
from research_agent.logger import StepLogger
from research_agent.search import SearchResult, web_search
from research_agent.trace import RunTrace

TOTAL_STEPS = 4


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
    trace: dict | None = None


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
    def __init__(self, llm: LLM | None = None):
        self.llm = llm or LLM()
        # A no-op logger until research() sets one up for the specific run.
        self.log = StepLogger(enabled=False)

    def plan(self, topic: str) -> list[str]:
        """Ask the LLM for a handful of focused search queries."""
        self.log.info(f"model: {self.llm.model}  (via Ollama)")
        self.log.wait("asking the model to draft search queries...")
        raw = self.llm.chat(
            system=PLANNER_SYSTEM,
            user=f"Topic: {topic}\n\nGive {config.NUM_SUBQUESTIONS} search queries.",
        )
        queries = [q.strip("-* \t") for q in raw.splitlines() if q.strip()]
        queries = [q for q in queries if q][: config.NUM_SUBQUESTIONS]
        # Always include the raw topic as a fallback query.
        if topic not in queries:
            queries.insert(0, topic)
        for i, q in enumerate(queries, 1):
            self.log.ok(f"query {i}: {q}")
        return queries

    def search_candidates(self, queries: list[str]) -> list[SearchResult]:
        """Run each query on the web and collect unique candidate links."""
        seen: set[str] = set()
        candidates: list[SearchResult] = []
        for q in queries:
            self.log.wait(f"searching the web for: {q}")
            found = web_search(q)
            new = 0
            for res in found:
                if res.url not in seen:
                    seen.add(res.url)
                    candidates.append(res)
                    new += 1
            self.log.ok(f"{len(found)} result(s), {new} new link(s)")
        self.log.info(
            f"total {len(candidates)} unique link(s); will read up to "
            f"{config.MAX_SOURCES}"
        )
        return candidates

    def read_sources(self, candidates: list[SearchResult]) -> list[Source]:
        """Open up to MAX_SOURCES candidate pages and extract their text."""
        sources: list[Source] = []
        for res in candidates:
            if len(sources) >= config.MAX_SOURCES:
                break
            self.log.wait(f"opening: {res.url}")
            text = fetch_text(res.url)
            if text:
                sources.append(Source(title=res.title, url=res.url, text=text))
                self.log.ok(f"read {len(text)} chars  <- {res.title[:50]}")
            else:
                self.log.skip(f"could not read (skipped): {res.url}")
        return sources

    def synthesize(self, topic: str, sources: list[Source]) -> str:
        """Combine sources into a cited report."""
        if not sources:
            self.log.skip("no readable sources -> cannot write a report")
            return (
                "No readable sources were retrieved for this topic. "
                "Try a different query or check your internet connection."
            )

        blocks = []
        for i, s in enumerate(sources, 1):
            blocks.append(f"[{i}] {s.title} ({s.url})\n{s.text}")
        corpus = "\n\n---\n\n".join(blocks)

        total_chars = sum(len(s.text) for s in sources)
        self.log.info(
            f"feeding {len(sources)} source(s) (~{total_chars} chars) to the model"
        )
        self.log.wait("model is writing the report (this is the slow part)...")

        user = (
            f"Topic: {topic}\n\n"
            f"Sources:\n\n{corpus}\n\n"
            "Write the research report now."
        )
        return self.llm.chat(system=SYNTHESIS_SYSTEM, user=user, temperature=0.3)

    def research(
        self, topic: str, verbose: bool = True, log_sink=None
    ) -> ResearchResult:
        # Logging is set per run so one shared (singleton) agent can serve the
        # terminal (verbose), the web UI (verbose + sink), and Claude (quiet).
        self.log = StepLogger(enabled=verbose, sink=log_sink)
        trace = RunTrace(topic, self.llm.model)
        self.log.start(topic)

        self.log.step(1, TOTAL_STEPS, "PLAN", "turn your topic into search queries")
        with trace.step("plan"):
            queries = self.plan(topic)
        trace.add_tokens(**self.llm.last_tokens)
        trace.metric("num_queries", len(queries))
        self.log.step_done(f"{len(queries)} query(ies) ready")

        self.log.step(2, TOTAL_STEPS, "SEARCH", "look those queries up on the web")
        with trace.step("search"):
            candidates = self.search_candidates(queries)
        trace.metric("candidate_links", len(candidates))
        self.log.step_done(f"{len(candidates)} candidate link(s) found")

        self.log.step(3, TOTAL_STEPS, "READ", "open pages and extract their text")
        with trace.step("read"):
            sources = self.read_sources(candidates)
        trace.metric("sources_read", len(sources))
        self.log.step_done(f"{len(sources)} readable source(s) collected")

        self.log.step(4, TOTAL_STEPS, "WRITE", "synthesize a cited report")
        with trace.step("write"):
            report = self.synthesize(topic, sources)
        trace.add_tokens(**self.llm.last_tokens)
        trace.metric("report_chars", len(report))
        self.log.step_done(f"report is {len(report)} chars")

        trace.sources = [{"title": s.title, "url": s.url} for s in sources]
        self.log.finish()

        return ResearchResult(
            topic=topic,
            subquestions=queries,
            report=report,
            sources=sources,
            trace=trace.summary(),
        )
