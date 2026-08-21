"""Simple web UI for the AI Research Agent.

Run:  python web.py   then open http://127.0.0.1:5000

The browser sends a topic, the server runs the agent in a background thread and
streams live progress back with Server-Sent Events (SSE), then shows the report
with links to download the generated Markdown and PDF.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading

import markdown as _markdown
from flask import (
    Flask,
    Response,
    render_template,
    request,
    send_from_directory,
)

import config
from research_agent.agent import ResearchAgent
from research_agent.llm import LLM
from research_agent.report import save_report

app = Flask(__name__)

# Quiet Flask's per-request HTTP lines ("GET /research ... 200") so the agent's
# own step-by-step logs are the only thing shown in the terminal.
logging.getLogger("werkzeug").setLevel(logging.ERROR)


@app.route("/")
def index():
    return render_template("index.html", model=config.OLLAMA_MODEL)


@app.route("/research")
def research():
    topic = (request.args.get("topic") or "").strip()

    def generate():
        if not topic:
            yield _sse("error", "Please enter a topic to research.")
            return

        q: queue.Queue = queue.Queue()

        def sink(line: str) -> None:
            q.put(("log", line))

        def worker() -> None:
            try:
                llm = LLM()
                ok, msg = llm.is_available()
                if not ok:
                    q.put(("error", msg))
                    return
                agent = ResearchAgent(llm=llm, verbose=True, log_sink=sink)
                result = agent.research(topic)

                sources = [(s.title, s.url) for s in result.sources]
                md_path, pdf_path = save_report(
                    result.topic, result.report, sources
                )
                report_html = _markdown.markdown(
                    result.report,
                    extensions=["extra", "sane_lists", "nl2br"],
                )
                q.put(
                    (
                        "done",
                        {
                            "report_html": report_html,
                            "md": os.path.basename(md_path),
                            "pdf": os.path.basename(pdf_path) if pdf_path else None,
                            "sources": sources,
                        },
                    )
                )
            except Exception as exc:  # noqa: BLE001 - surface any error to the UI
                q.put(("error", str(exc)))
            finally:
                q.put(("end", None))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, data = q.get()
            if kind == "end":
                break
            yield _sse(kind, data)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # disable proxy buffering for live streaming
    }
    return Response(generate(), mimetype="text/event-stream", headers=headers)


@app.route("/download/<path:name>")
def download(name: str):
    return send_from_directory(
        os.path.abspath(config.REPORTS_DIR), name, as_attachment=True
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


if __name__ == "__main__":
    print("AI Research Agent UI -> http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
