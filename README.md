# AI Research Agent

A local, privacy-friendly research agent. Give it a topic and it will:

1. **Plan** — use a local [Ollama](https://ollama.com) model to break the topic into focused search queries.
2. **Search** — query the web via DuckDuckGo (no API key required).
3. **Read** — fetch the top pages and extract their readable text.
4. **Synthesize** — write a clear, cited Markdown report using only what it read.

The LLM backend is **pluggable**: run it fully locally with [Ollama](https://ollama.com)
(no API keys), or point it at the **Anthropic** cloud API for production — the same
agent runs unchanged against either.

It ships two ways to run:

- **Single-file / local** — a CLI, an MCP server, and a simple web UI (this is the
  quick-start below).
- **Production platform** — a horizontally-scalable stack with a REST API, API-key
  auth, multi-tenancy, a background job queue, a Postgres-backed store, rate
  limiting, structured logs, Prometheus metrics, and a one-command Docker
  deployment. See **[Production deployment](#production-deployment-docker)**.

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

## Two flavours: hand-built vs LangChain

This repo ships the same idea built two ways, so you can compare them:

| | Hand-built (`research_agent/`) | LangChain (`langchain_agent.py`) |
|---|---|---|
| Steps | Fixed pipeline we coded: plan → search → read → write | The model decides when to search, read, and write |
| Control | Full — every step is visible | The framework runs the loop |
| Dependencies | Tiny | Adds `langchain-ollama`, `langgraph` |

Run the LangChain version:

```bash
pip install langchain-ollama langgraph
python langchain_agent.py "benefits of green tea"
```

It prints each decision the agent makes (which tool it calls) so you can watch
it think. Everything else in this README describes the hand-built version, which
powers the CLI, web UI, and MCP server.

## Run with Docker

`docker compose up -d --build` brings up the full production stack (nginx, web,
worker, Postgres, Redis, and Ollama with an automatic model pull). See
**[Production deployment](#production-deployment-docker)** for the complete
walkthrough, including switching to the Anthropic cloud model and minting API
keys.

The first run downloads the Ollama model (~2GB) into a named volume, so later
runs start instantly. Ollama in Docker runs on CPU unless a GPU is configured,
so responses are slower than a native GPU install — or set
`LLM_PROVIDER=anthropic` to offload generation to the cloud.

## Web UI

Prefer a browser over the terminal? Run the web app:

```bash
python web.py
```

Then open <http://127.0.0.1:5000>. Type a topic, click **Research**, and watch
live progress stream in the page while it works. When it finishes you get the
report on screen plus buttons to download the Markdown and PDF. Stop the server
with `Ctrl + C`.

> The web UI and REST API share one background job queue, so they need Redis, a
> database, and at least one worker running. The easiest way to get all of that
> is the Docker stack below; for running the pieces by hand see
> [Running the platform without Docker](#running-the-platform-without-docker).

## Production deployment (Docker)

The production stack runs on a single VM with one command. It brings up:

| Service | Role |
|---|---|
| **nginx** | TLS-terminating reverse proxy, SSE-aware (buffering off, long timeouts) |
| **web** (gunicorn) | REST API + browser UI + auth + rate limiting |
| **worker** (RQ) | Runs research jobs off the request thread |
| **postgres** | Durable store: tenants, API keys, jobs, reports, traces |
| **redis** | Job queue + live-progress pub/sub + rate-limit storage |
| **ollama** | Local model server (skip when using the Anthropic provider) |

```
Client ─► nginx ─► gunicorn/Flask ──enqueue──► Redis ──► RQ worker ──► LLM
                        │  subscribe progress ◄────────────┘   │
                        └──────────── Postgres ◄───────────────┘
```

### 1. Configure

```bash
cp .env.example .env
# Set a strong SECRET_KEY, DB password, and choose the LLM provider.
python -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
```

To use the cloud model instead of Ollama, set in `.env`:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
```

### 2. Launch

```bash
docker compose up -d --build
```

Migrations run automatically on the web container's start. The app is served
through nginx at <http://localhost:8080> (change with `HTTP_PORT`). Check health:

```bash
curl http://localhost:8080/healthz     # liveness
curl http://localhost:8080/readyz      # DB + Redis readiness
curl http://localhost:8080/metrics     # Prometheus metrics
```

### 3. Create a tenant + API key

The REST API requires an API key (`REQUIRE_API_KEY=true`). Mint one:

```bash
docker compose exec web python -m app.cli create-tenant "Acme Corp"
docker compose exec web python -m app.cli create-key --tenant <tenant_id> --name prod
# -> prints the raw key ONCE. Store it now.
```

Put nginx behind TLS (a certificate on the host, or a proxy like Caddy/Traefik)
before exposing it to the internet.

## REST API

All `/api/v1` endpoints are tenant-scoped. Authenticate with
`Authorization: Bearer <api-key>` (or `X-API-Key: <api-key>`).

| Method & path | Description |
|---|---|
| `POST /api/v1/research` | Enqueue a job. Body: `{"topic": "...", "provider"?, "model"?}`. Returns `202` + job. |
| `GET /api/v1/research` | List this tenant's jobs (`?limit=&offset=`). |
| `GET /api/v1/research/{id}` | Job status + metadata. |
| `GET /api/v1/research/{id}/report` | Full report (markdown, html, sources, trace) once ready. |
| `GET /api/v1/research/{id}/report.md` | Download Markdown. |
| `GET /api/v1/research/{id}/report.pdf` | Download PDF (rendered on demand). |
| `GET /api/v1/research/{id}/stream` | Live progress via Server-Sent Events. |

```bash
KEY=rak_your_key_here

# Start a job
curl -s -X POST http://localhost:8080/api/v1/research \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"topic":"impact of caffeine on sleep"}'

# Poll status, then fetch the report
curl -s http://localhost:8080/api/v1/research/$ID \
  -H "Authorization: Bearer $KEY"
curl -s http://localhost:8080/api/v1/research/$ID/report \
  -H "Authorization: Bearer $KEY"
```

Rate limits apply per API key (default `60/min`, `10/min` for job creation) and
are configurable via `RATE_LIMIT_DEFAULT` / `RATE_LIMIT_RESEARCH`.

## Running the platform without Docker

You need Postgres and Redis reachable. Then, in separate terminals:

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://research:research@localhost:5432/research
export REDIS_URL=redis://localhost:6379/0

alembic upgrade head            # create the schema
python -m app.jobs.worker       # terminal 1: the worker
python web.py                   # terminal 2: the web app (waitress)
```

For a zero-infrastructure spin-up (SQLite, no queue), the CLI can still run a
single job inline: `python -m app.cli research "your topic"`.

## Observability

Every run records what it did — no cloud, no keys, all local:

- **Terminal / CLI**: prints a summary (per-step timings, token counts, how many
  pages were read) and writes a JSON trace to `traces/`.
- **Web UI**: shows the same numbers as stat cards above the report.
- **Trace files** (`traces/*.json`) capture per-run timings, metrics, tokens, and
  the sources used — handy for spotting the slow step (usually WRITE) or
  comparing models.

Example summary:

```
observability ------------------------------------------
  model         : llama3.2
  total time    : 207.2s
  step plan   : 3.7s
  step search : 13.1s
  step read   : 7.1s
  step write  : 183.3s
  queries=4  links=15  read=6  report_chars=4381
  tokens        : prompt=2132 output=914
```

## Evals

Measure quality instead of eyeballing PDFs. The eval harness runs the agent on
a set of topics and auto-checks each report:

```bash
python evals.py                      # built-in test cases
python evals.py --topic "..."        # one ad-hoc topic
python evals.py --model llama3.2     # test a specific model
```

Each run is scored on: `no_error`, `has_report`, `read_2plus` (read ≥2 pages),
`cites_sources` (uses `[n]` citations), and `on_topic`. It prints a scoreboard
and saves JSON to `eval_results/`. Use it to compare models or prompt changes —
e.g. run it on the local model now, then again after moving to a bigger model.

```
EVAL SCOREBOARD  |  model: llama3.2
topic                               score    time  read  tok_out
benefits of green tea             4/    5 186.5s     6      902
overall checks passed: 4/5  (80%)
```

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

All configuration is validated at startup (see `app/settings.py`) and read from
environment variables or a `.env` file. Key settings:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | LLM backend: `ollama` or `anthropic` |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model to use |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=anthropic` |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | Cloud model to use |
| `DATABASE_URL` | `postgresql+psycopg://…` | SQLAlchemy database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for queue + pub/sub + limits |
| `SECRET_KEY` | `dev-insecure…` | **Override in production** |
| `REQUIRE_API_KEY` | `true` | Require an API key on the REST API |
| `RATE_LIMIT_DEFAULT` | `60/minute` | Default per-key/IP rate limit |
| `RATE_LIMIT_RESEARCH` | `10/minute` | Rate limit for job creation |
| `LOG_JSON` | `true` | JSON logs (`false` = pretty console) |
| `RESEARCH_SEARCH_RESULTS` | `5` | Results per search query |
| `RESEARCH_SUBQUESTIONS` | `3` | Sub-queries the planner generates |
| `RESEARCH_MAX_SOURCES` | `6` | Max pages fetched per run |
| `RESEARCH_MAX_SOURCE_CHARS` | `6000` | Chars of each page fed to the model |

## Project structure

```
AI-Research-Agent/
├── wsgi.py                    # Production WSGI entrypoint (gunicorn)
├── web.py                     # Local web runner (waitress)
├── main.py                    # Legacy CLI entry point
├── mcp_server.py              # MCP server (use the agent from Claude)
├── config.py                  # Backward-compat facade over app.settings
├── pyproject.toml             # Packaging, deps, tooling
├── alembic.ini / migrations/  # Database migrations
├── docker-compose.yml         # Full stack for a single VM
├── Dockerfile                 # Multi-stage, non-root runtime image
├── deploy/                    # gunicorn, nginx, entrypoint
├── templates/index.html       # Browser UI page
├── tests/                     # pytest suite (SQLite + fakeredis, no network)
│
├── app/                       # Production application
│   ├── settings.py            # Validated configuration (pydantic-settings)
│   ├── cli.py                 # Admin CLI (tenants, keys, init-db, research)
│   ├── llm/                   # Pluggable providers: base, ollama, anthropic, factory
│   ├── db/                    # SQLAlchemy models, sessions, repository
│   ├── auth/                  # API-key generation/hashing + request guard
│   ├── jobs/                  # Redis/RQ queue, worker, live-progress pub/sub
│   ├── observability/         # structlog logging + Prometheus metrics
│   └── api/                   # Flask factory: REST API, UI, health, errors
│
└── research_agent/            # Core domain logic (LLM-agnostic)
    ├── agent.py               # Orchestration: plan -> search -> read -> synthesize
    ├── singletons.py          # Shared, reused provider + agent instances
    ├── trace.py               # Per-run observability (timings, tokens, metrics)
    ├── search.py              # DuckDuckGo web search
    ├── fetch.py               # URL fetch + text extraction
    └── report.py              # Markdown / HTML / PDF rendering
```

## Testing & CI

```bash
pip install -e ".[dev]"
pytest              # runs fully offline (SQLite + fakeredis + stub LLM)
ruff check .        # lint
```

GitHub Actions (`.github/workflows/ci.yml`) runs lint, tests, a migration check,
and a Docker build on every push and PR.

## How it works

The agent is a simple, transparent pipeline rather than a black box — each stage
lives in its own module. The production layers (`app/`) wrap that core without
changing it: the agent depends only on a small `LLMProvider` interface, so the
same pipeline runs against a local Ollama model or the Anthropic cloud API, from
the CLI, the web UI, the REST API, or an MCP client.
