"""Backward-compatible flat configuration facade.

Historically the codebase used ``import config; config.OLLAMA_MODEL``. The real,
validated configuration now lives in :mod:`app.settings`; this module re-exports
those values under the original names so existing imports keep working.

Prefer ``from app.settings import get_settings`` in new code.
"""

from app.settings import get_settings

_s = get_settings()

# --- LLM (active provider) ---
OLLAMA_HOST = _s.ollama_host
OLLAMA_MODEL = _s.ollama_model
LLM_PROVIDER = _s.llm_provider

# --- Research behaviour ---
SEARCH_RESULTS = _s.search_results
NUM_SUBQUESTIONS = _s.num_subquestions
MAX_SOURCES = _s.max_sources
MAX_SOURCE_CHARS = _s.max_source_chars

# --- Networking ---
HTTP_TIMEOUT = _s.http_timeout
USER_AGENT = _s.user_agent

# --- Output ---
REPORTS_DIR = _s.reports_dir
TRACES_DIR = _s.traces_dir
