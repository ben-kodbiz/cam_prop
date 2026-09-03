"""Real RSS ingestion pipeline.

Fetches configured feeds (data/feeds.json), extracts entries, registers new
sources in the database (hashed + archived), and skips duplicates. Network
calls are rate-limited per host. Nothing here publishes anything: ingested
sources merely become available for evidence linking and review.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from ingestion import rss

from app.sources import DuplicateSourceError, create_source

DEFAULT_FEEDS_PATH = Path(__file__).resolve().parent.parent / "data" / "feeds.json"


@dataclass
class FeedConfig:
    name: str
    url: str
    source_type: str = "news"
    enabled: bool = True


@dataclass
class FeedResult:
    feed: str
    discovered: int = 0
    registered: int = 0
    duplicates: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "feed": self.feed,
            "discovered": self.discovered,
            "registered": self.registered,
            "duplicates": self.duplicates,
            "errors": self.errors,
            "error_details": self.error_details,
        }


def load_feeds(path: str | Path = DEFAULT_FEEDS_PATH) -> list[FeedConfig]:
    """Read feed configuration. Feeds set to enabled=false are skipped."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    feeds = []
    for entry in data.get("feeds", []):
        if not entry.get("url"):
            continue
        feeds.append(
            FeedConfig(
                name=entry.get("name") or entry["url"],
                url=entry["url"],
                source_type=entry.get("source_type", "news"),
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return [f for f in feeds if f.enabled]


def ingest_feed(
    conn: sqlite3.Connection,
    feed: FeedConfig,
    *,
    archive_dir: Path | None = None,
    fetcher: Callable[[str], tuple[str, bytes]] | None = None,
) -> FeedResult:
    """Ingest one feed. `fetcher` (url -> (text, bytes)) is injectable for tests."""
    result = FeedResult(feed=feed.name)
    try:
        raw = b""
        items: list[dict[str, Any]] = []
        if fetcher is not None:
            text, raw = fetcher(feed.url)
            items = rss.parse_feed(text)
        else:
            items = [
                {
                    "url": i.url,
                    "title": i.title,
                    "publisher": i.publisher,
                    "published_at": i.published_at,
                }
                for i in rss.discover(feed.url)  # network path
            ]
    except Exception as e:
        result.errors += 1
        result.error_details.append(f"fetch failed: {e}")
        return result

    for item in items:
        url = item.get("url") or ""
        if not url:
            continue
        result.discovered += 1
        title = item.get("title") or url
        try:
            create_source(
                conn,
                url=url,
                title=title,
                source_type=feed.source_type,
                publisher=item.get("publisher"),
                published_at=_iso_date(item.get("published_at")),
                content=raw or None,
                content_text=None if raw else (item.get("summary") or title),
                archive_dir=archive_dir,
            )
            result.registered += 1
        except DuplicateSourceError:
            result.duplicates += 1
        except Exception as e:
            result.errors += 1
            result.error_details.append(f"{url}: {e}")
    return result


def ingest_all(
    conn: sqlite3.Connection,
    *,
    feeds_path: str | Path = DEFAULT_FEEDS_PATH,
    archive_dir: Path | None = None,
    fetcher: Callable[[str], tuple[str, bytes]] | None = None,
) -> list[FeedResult]:
    """Ingest every enabled feed; one failing feed never aborts the rest."""
    results = []
    for feed in load_feeds(feeds_path):
        results.append(ingest_feed(conn, feed, archive_dir=archive_dir, fetcher=fetcher))
    return results


def _iso_date(value: str | None) -> str | None:
    """Best-effort RFC822 -> ISO date; returns None when unparsable."""
    if not value:
        return None

    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.date().isoformat()
    except (TypeError, ValueError):
        return None
