"""Central configuration for the AI Research Agent.

Values can be overridden with environment variables so nothing is hard-coded
for a particular machine.
"""

import os

# --- Ollama (local LLM) ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# --- Research behaviour ---
# How many web results to pull per search query.
SEARCH_RESULTS = int(os.getenv("RESEARCH_SEARCH_RESULTS", "5"))
# How many sub-questions the planner generates for a topic.
NUM_SUBQUESTIONS = int(os.getenv("RESEARCH_SUBQUESTIONS", "3"))
# Max pages actually fetched and read across the whole run.
MAX_SOURCES = int(os.getenv("RESEARCH_MAX_SOURCES", "6"))
# Max characters of extracted page text fed to the model per source.
MAX_SOURCE_CHARS = int(os.getenv("RESEARCH_MAX_SOURCE_CHARS", "6000"))

# --- Networking ---
HTTP_TIMEOUT = int(os.getenv("RESEARCH_HTTP_TIMEOUT", "20"))
USER_AGENT = os.getenv(
    "RESEARCH_USER_AGENT",
    "AI-Research-Agent/0.1 (+https://github.com/kiranmuli/AI-Research-Agent)",
)

# --- Output ---
REPORTS_DIR = os.getenv("RESEARCH_REPORTS_DIR", "reports")

# --- Observability ---
# Where per-run JSON traces (timings, token counts, step metrics) are written.
TRACES_DIR = os.getenv("RESEARCH_TRACES_DIR", "traces")
