"""Ingestion tests: RSS parsing, HTML extraction, sitemap (no network)."""

from __future__ import annotations

import pytest
from ingestion.html import extract_text
from ingestion.rss import parse_feed
from ingestion.sitemap import parse_sitemap

RSS_SAMPLE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Example Feed</title>
  <item>
    <title>First item</title>
    <link>https://example.org/first?utm_source=feed</link>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second item</title>
    <link>https://example.org/second</link>
  </item>
</channel></rss>"""

SITEMAP_SAMPLE = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.org/a</loc><lastmod>2024-01-01</lastmod></url>
  <url><loc>https://example.org/b</loc></url>
</urlset>"""


def test_parse_feed_items():
    items = parse_feed(RSS_SAMPLE)
    assert len(items) == 2
    assert items[0]["title"] == "First item"
    assert items[0]["publisher"] == "Example Feed"
    assert "utm_source" in items[0]["url"]  # canonicalization happens in discover()


def test_extract_text_strips_scripts():
    html = """<html><head><style>.x{}</style></head><body>
    <script>alert('x')</script><!-- comment -->
    <h1>Headline</h1><p>Body paragraph &amp; more.</p></body></html>"""
    text = extract_text(html)
    assert "Headline" in text
    assert "Body paragraph & more" in text
    assert "alert" not in text
    assert "{}" not in text


def test_parse_sitemap():
    urls = parse_sitemap(SITEMAP_SAMPLE)
    assert [u["loc"] for u in urls] == ["https://example.org/a", "https://example.org/b"]
    assert urls[0]["lastmod"] == "2024-01-01"


def test_parse_sitemap_invalid():
    with pytest.raises(Exception, match="invalid sitemap"):
        parse_sitemap("<not-xml")


def test_rate_limiter_respects_host_delay():
    import time

    from ingestion.rss import MIN_INTERVAL_PER_HOST, _RateLimiter

    limiter = _RateLimiter()
    start = time.monotonic()
    limiter.wait("https://a.example/1")
    limiter.wait("https://b.example/1")  # different host: no wait
    limiter.wait("https://a.example/2")  # same host: waits
    elapsed = time.monotonic() - start
    assert elapsed >= MIN_INTERVAL_PER_HOST * 0.9
