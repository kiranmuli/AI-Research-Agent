"""Write research results to Markdown and PDF report files."""

from __future__ import annotations

import html
import os
import re
from datetime import datetime

import markdown as _markdown
from xhtml2pdf import pisa

import config

Sources = list[tuple[str, str]]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "report"


def _base_path(topic: str) -> str:
    """Shared path (without extension) so the .md and .pdf names match."""
    os.makedirs(config.REPORTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(config.REPORTS_DIR, f"{stamp}-{_slugify(topic)}")


def _meta_line() -> str:
    return (
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} "
        f"| model: {config.OLLAMA_MODEL}"
    )


def _markdown_document(topic: str, body: str, sources: Sources) -> str:
    lines = [
        f"# Research Report: {topic}",
        "",
        f"*{_meta_line()}*",
        "",
        body.strip(),
        "",
        "## Sources",
        "",
    ]
    if sources:
        for i, (title, url) in enumerate(sources, 1):
            lines.append(f"{i}. [{title}]({url})")
    else:
        lines.append("_No sources retrieved._")
    lines.append("")
    return "\n".join(lines)


# --- CSS for the PDF (a subset xhtml2pdf understands) ---------------------
_PDF_CSS = """
@page { size: A4; margin: 2.2cm 2cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 11pt;
       color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 22pt; color: #0b5cad; margin: 0 0 4pt 0; }
h2 { font-size: 15pt; color: #0b5cad; border-bottom: 1px solid #d0d7de;
     padding-bottom: 3pt; margin-top: 18pt; }
h3 { font-size: 12.5pt; color: #333; margin-top: 14pt; }
p  { margin: 6pt 0; }
ul, ol { margin: 6pt 0 6pt 14pt; }
li { margin: 3pt 0; }
a { color: #0b5cad; text-decoration: none; }
.meta { color: #6a737d; font-size: 9pt; margin-bottom: 10pt; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 10pt 0; }
strong { color: #111; }
blockquote { color: #555; border-left: 3px solid #d0d7de;
             margin: 6pt 0; padding-left: 10pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
th, td { border: 1px solid #d0d7de; padding: 4pt 6pt; font-size: 10pt; }
th { background: #f2f5f8; }
"""


# The default PDF font (Helvetica) can't render some Unicode punctuation, so
# map the common ones the model tends to emit to plain ASCII for the PDF only.
_ASCII_MAP = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "*",
    " ": " ", "−": "-",
}


def _ascii_safe(text: str) -> str:
    for bad, good in _ASCII_MAP.items():
        text = text.replace(bad, good)
    return text


def _html_document(topic: str, body: str, sources: Sources) -> str:
    body_html = _markdown.markdown(
        _ascii_safe(body.strip()), extensions=["extra", "sane_lists", "nl2br"]
    )
    source_items = ""
    if sources:
        # Escape url/title: they come from web results and may contain HTML.
        rows = "".join(
            f'<li><a href="{html.escape(url)}">'
            f"{html.escape(_ascii_safe(title))}</a></li>"
            for title, url in sources
        )
        source_items = f"<ol>{rows}</ol>"
    else:
        source_items = "<p><em>No sources retrieved.</em></p>"

    return f"""<html>
<head><meta charset="utf-8"><style>{_PDF_CSS}</style></head>
<body>
  <h1>Research Report</h1>
  <p class="meta">{html.escape(_ascii_safe(topic))}<br/>{_meta_line()}</p>
  <hr/>
  {body_html}
  <h2>Sources</h2>
  {source_items}
</body>
</html>"""


def save_markdown(topic: str, body: str, sources: Sources, base: str) -> str:
    path = base + ".md"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_markdown_document(topic, body, sources))
    return path


def save_pdf(topic: str, body: str, sources: Sources, base: str) -> str | None:
    path = base + ".pdf"
    html_doc = _html_document(topic, body, sources)
    try:
        with open(path, "wb") as fh:
            result = pisa.CreatePDF(src=html_doc, dest=fh, encoding="utf-8")
        if result.err:
            raise RuntimeError("xhtml2pdf reported an error")
    except Exception:
        # Never leave a broken/empty .pdf behind on any failure path.
        if os.path.exists(path):
            os.remove(path)
        return None
    return path


def save_report(topic: str, body: str, sources: Sources) -> tuple[str, str | None]:
    """Write both a Markdown and a PDF report; return (md_path, pdf_path).

    pdf_path is None if PDF generation failed for any reason.
    """
    base = _base_path(topic)
    md_path = save_markdown(topic, body, sources, base)
    try:
        pdf_path = save_pdf(topic, body, sources, base)
    except Exception:  # noqa: BLE001 - PDF is a nice-to-have, never fatal
        pdf_path = None
    return md_path, pdf_path
