"""Sitemap-based discovery of additional source URLs."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ingestion.rss import fetch


def parse_sitemap(xml_text: str) -> list[dict[str, str | None]]:
    """Parse a sitemap XML into URL entries (loc, lastmod)."""
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        msg = f"invalid sitemap XML: {e}"
        raise SitemapError(msg) from e
    urls = []
    for url_el in root.findall("sm:url", ns):
        loc = url_el.findtext("sm:loc", default=None, namespaces=ns)
        lastmod = url_el.findtext("sm:lastmod", default=None, namespaces=ns)
        if loc:
            urls.append({"loc": loc.strip(), "lastmod": lastmod})
    return urls


class SitemapError(ValueError):
    pass


def discover(sitemap_url: str) -> list[dict[str, str | None]]:
    resp = fetch(sitemap_url)
    return parse_sitemap(resp.text)


def looks_like_sitemap(content: str) -> bool:
    return bool(re.match(r"\s*<\?xml|<urlset", content))
