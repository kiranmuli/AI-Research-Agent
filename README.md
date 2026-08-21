# AI Research Agent

A local, privacy-friendly research agent. Give it a topic and it will:

1. **Plan** — use a local [Ollama](https://ollama.com) model to break the topic into focused search queries.
2. **Search** — query the web via DuckDuckGo (no API key required).
3. **Read** — fetch the top pages and extract their readable text.
4. **Synthesize** — write a clear, cited Markdown report using only what it read.

The LLM runs entirely on your machine through Ollama — no cloud API keys needed.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) running locally with a model pulled, e.g.:
  ```bash
  ollama pull llama3.2
  ```

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

```bash
python main.py "impact of caffeine on sleep quality"
```

Options:

```bash
python main.py "topic" --model llama3.2   # choose a different Ollama model
python main.py "topic" --no-save          # print only, don't write a file
python main.py "topic" --quiet            # hide progress logs
```

Reports are written to the `reports/` directory as timestamped Markdown files.

## Configuration

Behaviour is controlled by environment variables (see `config.py` for defaults):

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Model to use |
| `RESEARCH_SEARCH_RESULTS` | `5` | Results per search query |
| `RESEARCH_SUBQUESTIONS` | `3` | Sub-queries the planner generates |
| `RESEARCH_MAX_SOURCES` | `6` | Max pages fetched per run |
| `RESEARCH_MAX_SOURCE_CHARS` | `6000` | Chars of each page fed to the model |

## Project structure

```
AI-Research-Agent/
├── main.py                 # CLI entry point
├── config.py               # Configuration + env overrides
├── requirements.txt
└── research_agent/
    ├── agent.py            # Orchestration: plan -> search -> read -> synthesize
    ├── llm.py              # Local Ollama client
    ├── search.py           # DuckDuckGo web search
    ├── fetch.py            # URL fetch + text extraction
    └── report.py           # Markdown report writer
```

## How it works

The agent is a simple, transparent pipeline rather than a black box — each stage
lives in its own module so you can swap the search backend, change the model, or
adjust how sources are read without touching the rest.
