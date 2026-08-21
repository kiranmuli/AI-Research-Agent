"""Fetch a URL and extract readable text."""

from __future__ import annotations

import requests
from bs4 import BeautifulSoup

import config


def fetch_text(url: str) -> str | None:
    """Download a page and return cleaned, readable text (or None on failure)."""
    try:
        resp = requests.get(
            url,
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
        )
        resp.raise_for_status()
    except requests.RequestException:
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "html" not in content_type and content_type:
        # Skip PDFs, images, etc. — this agent only reads HTML pages.
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Drop non-content elements before extracting text.
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse blank lines / whitespace.
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)

    return cleaned[: config.MAX_SOURCE_CHARS] if cleaned else None
