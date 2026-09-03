"""RSS feed discovery. Polite fetching with per-host rate limits."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import feedparser
import httpx
from app.util import canonicalize_url

USER_AGENT = "open-evidence/0.1 (+research; respects robots.txt)"
MIN_INTERVAL_PER_HOST = 5.0  # seconds between requests to the same host
TIMEOUT = 20.0


@dataclass
class DiscoveredItem:
    url: str
    title: str
    publisher: str | None
    published_at: str | None
    source_id_hint: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class _RateLimiter:
    def __init__(self) -> None:
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        from urllib.parse import urlsplit

        host = urlsplit(url).hostname or ""
        now = time.monotonic()
        last = self._last.get(host, 0.0)
        delta = now - last
        if delta < MIN_INTERVAL_PER_HOST:
            time.sleep(MIN_INTERVAL_PER_HOST - delta)
        self._last[host] = time.monotonic()


_limiter = _RateLimiter()


def fetch(url: str, *, limiter: _RateLimiter | None = None) -> httpx.Response:
    """GET with rate limiting. Raises httpx errors on failure."""
    (limiter or _limiter).wait(url)
    with httpx.Client(
        follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp


def parse_feed(xml_text: str) -> list[dict[str, Any]]:
    """Parse RSS/Atom text into raw item dicts (no network)."""
    feed = feedparser.parse(xml_text)
    items = []
    for entry in feed.entries:
        link = entry.get("link") or ""
        items.append(
            {
                "url": link,
                "title": entry.get("title") or "",
                "publisher": feed.feed.get("title"),
                "published_at": entry.get("published") or entry.get("updated"),
            }
        )
    return items


def discover(feed_url: str) -> list[DiscoveredItem]:
    """Fetch a feed and return discovered items (canonical URLs)."""
    resp = fetch(feed_url)
    return [
        DiscoveredItem(
            url=canonicalize_url(i["url"]),
            title=i["title"],
            publisher=i["publisher"],
            published_at=i["published_at"],
        )
        for i in parse_feed(resp.text)
        if i["url"]
    ]
