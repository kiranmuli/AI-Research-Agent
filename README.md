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

## Web UI

Prefer a browser over the terminal? Run the web app:

```bash
python web.py
```

Then open <http://127.0.0.1:5000>. Type a topic, click **Research**, and watch
live progress stream in the page while it works. When it finishes you get the
report on screen plus buttons to download the Markdown and PDF. Stop the server
with `Ctrl + C`.

## Use it from Claude (MCP server)

You can plug this agent into **Claude Desktop** or **Claude Code** as an MCP
server. Then, inside Claude, just ask it to research something and it will call
your local agent behind the scenes.

The server (`mcp_server.py`) exposes two tools:

| Tool | What it does |
|---|---|
| `research(topic)` | Full pipeline: plan → search → read → write a cited report. |
| `web_search(query)` | Fast lookup: returns top web results (no reading/LLM). |

**Ollama must be running** while you use it.

### Claude Desktop

Edit `claude_desktop_config.json` (on Windows it's at
`%APPDATA%\Claude\claude_desktop_config.json`) and add:

```json
{
  "mcpServers": {
    "ai-research-agent": {
      "command": "C:\\Users\\Kiran.Muli\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",
      "args": ["D:\\Resarch Agent\\AI-Research-Agent\\mcp_server.py"],
      "cwd": "D:\\Resarch Agent\\AI-Research-Agent"
    }
  }
}
```

Then restart Claude Desktop. You should see the `research` and `web_search`
tools available. Try asking: *"Research the health benefits of green tea."*

### Claude Code

From the project folder, run:

```bash
claude mcp add ai-research-agent -- python mcp_server.py
```

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
├── web.py                  # Web UI (Flask, live progress)
├── mcp_server.py           # MCP server (use the agent from Claude)
├── templates/index.html    # Web UI page
├── config.py               # Configuration + env overrides
├── requirements.txt
└── research_agent/
    ├── agent.py            # Orchestration: plan -> search -> read -> synthesize
    ├── singletons.py       # Shared, reused LLM + agent instances
    ├── llm.py              # Local Ollama client
    ├── search.py           # DuckDuckGo web search
    ├── fetch.py            # URL fetch + text extraction
    └── report.py           # Markdown report writer
```

## How it works

The agent is a simple, transparent pipeline rather than a black box — each stage
lives in its own module so you can swap the search backend, change the model, or
adjust how sources are read without touching the rest.
