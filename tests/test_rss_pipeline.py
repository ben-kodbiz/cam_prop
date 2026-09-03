"""RSS pipeline tests (network mocked via injectable fetcher)."""

from __future__ import annotations

import json

import pytest
from app.rss_pipeline import FeedConfig, ingest_all, ingest_feed, load_feeds
from app.sources import create_source

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Wire</title>
  <item>
    <title>Court issues new order in ongoing case</title>
    <link>https://example.org/news/court-order?utm_source=rss</link>
    <pubDate>Tue, 27 Feb 2024 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Government publishes contract records</title>
    <link>https://example.org/news/contract-records</link>
    <pubDate>Wed, 28 Feb 2024 09:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Item without link is skipped</title>
  </item>
</channel></rss>"""


def _fetcher(url):
    return RSS_XML, b"<rss>raw</rss>"


def test_load_feeds_skips_disabled(tmp_path):
    feeds_file = tmp_path / "feeds.json"
    feeds_file.write_text(
        json.dumps(
            {
                "feeds": [
                    {"name": "a", "url": "https://a.example/feed", "enabled": True},
                    {"name": "b", "url": "https://b.example/feed", "enabled": False},
                    {"name": "c", "url": "https://c.example/feed"},
                ]
            }
        )
    )
    feeds = load_feeds(feeds_file)
    assert [f.name for f in feeds] == ["a", "c"]
    assert feeds[1].enabled is True  # default enabled


def test_load_feeds_default_path():
    feeds = load_feeds()  # repo data/feeds.json — all disabled placeholders
    assert feeds == []


def test_ingest_feed_registers_sources(tmp_db, tmp_path):
    feed = FeedConfig(name="wire", url="https://example.org/feed.xml", source_type="news")
    result = ingest_feed(tmp_db, feed, archive_dir=tmp_path / "archive", fetcher=_fetcher)
    assert result.discovered == 2
    assert result.registered == 2
    assert result.duplicates == 0
    assert result.errors == 0
    rows = tmp_db.execute("SELECT * FROM sources ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["source_type"] == "news"
    assert rows[0]["source_tier"] == 2
    # canonical URL stripped the tracking param
    assert rows[0]["canonical_url"] == "https://example.org/news/court-order"
    # pubDate parsed to ISO date
    assert rows[0]["published_at"] == "2024-02-27"


def test_ingest_feed_dedupes_on_second_run(tmp_db, tmp_path):
    feed = FeedConfig(name="wire", url="https://example.org/feed.xml")
    ingest_feed(tmp_db, feed, archive_dir=tmp_path / "archive", fetcher=_fetcher)
    result = ingest_feed(tmp_db, feed, archive_dir=tmp_path / "archive", fetcher=_fetcher)
    assert result.discovered == 2
    assert result.registered == 0
    assert result.duplicates == 2


def test_ingest_feed_fetch_error_recorded(tmp_db):
    def broken_fetcher(url):
        raise ConnectionError("network down")

    feed = FeedConfig(name="wire", url="https://example.org/feed.xml")
    result = ingest_feed(tmp_db, feed, fetcher=broken_fetcher)
    assert result.errors == 1
    assert "network down" in result.error_details[0]


def test_ingest_all_continues_after_feed_failure(tmp_db, tmp_path):
    feeds_file = tmp_path / "feeds.json"
    feeds_file.write_text(
        json.dumps(
            {
                "feeds": [
                    {"name": "bad", "url": "https://bad.example/feed"},
                    {"name": "good", "url": "https://good.example/feed"},
                ]
            }
        )
    )

    def fetcher(url):
        if "bad" in url:
            raise TimeoutError("boom")
        return RSS_XML, b"raw"

    results = ingest_all(tmp_db, feeds_path=feeds_file, fetcher=fetcher)
    assert len(results) == 2
    assert results[0].errors == 1
    assert results[1].registered == 2


def test_ingested_item_dedupes_against_manual_registration(tmp_db, tmp_path):
    create_source(
        tmp_db,
        url="https://example.org/news/contract-records",
        title="Manual",
        source_type="news",
        content_text="x",
    )
    feed = FeedConfig(name="wire", url="https://example.org/feed.xml")
    result = ingest_feed(tmp_db, feed, fetcher=_fetcher)
    assert result.registered == 1
    assert result.duplicates == 1


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Tue, 27 Feb 2024 12:00:00 GMT", "2024-02-27"),
        ("not a date", None),
        (None, None),
    ],
)
def test_iso_date_parsing(raw, expected):
    from app.rss_pipeline import _iso_date

    assert _iso_date(raw) == expected
