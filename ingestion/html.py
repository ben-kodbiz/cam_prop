"""HTML ingestion: fetch and extract readable main text."""

from __future__ import annotations

import re

from ingestion.rss import fetch


def extract_text(html: str) -> str:
    """Extract readable text from HTML without heavy dependencies.

    Strips script/style, tags, comments; collapses whitespace.
    Good enough for hashing, archiving and keyword search.
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(r"<(br|/p|/div|/h[1-6]|/li)[^>]*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;([0-9a-fA-F]{2});", r"&#\1;", text)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def ingest(url: str) -> tuple[str, bytes]:
    """Fetch a page, return (extracted_text, raw_bytes_for_hashing)."""
    resp = fetch(url)
    return extract_text(resp.text), resp.content
