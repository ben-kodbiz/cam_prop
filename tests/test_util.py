"""Utility tests: IDs, hashing, URL canonicalization, normalization."""

from __future__ import annotations

import sqlite3

import pytest
from app.util import (
    canonicalize_url,
    next_id,
    normalize_claim_text,
    sha256_bytes,
    sha256_text,
)


def test_sha256_stable():
    assert sha256_text("hello") == sha256_bytes(b"hello")
    assert len(sha256_text("hello")) == 64


def test_next_id_sequential(tmp_db):
    assert next_id(tmp_db, "sources", "SRC").endswith("0001")
    tmp_db.execute(
        "INSERT INTO sources (id, url, canonical_url, title, retrieved_at, source_tier,"
        " language, content_hash, created_at, updated_at)"
        " VALUES ('SRC-2026-0042', 'u', 'u', 't', '2024', 1, 'en', 'h', '2024', '2024')"
    )
    assert next_id(tmp_db, "sources", "SRC").endswith("0043")


def test_next_id_unknown_table():
    with pytest.raises(ValueError, match="unknown id prefix"):
        next_id(sqlite3.connect(":memory:"), "bogus", "X")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://Example.com/News/Article/", "https://example.com/News/Article"),
        ("https://example.com/a?utm_source=rss&fbclid=xyz&id=7", "https://example.com/a?id=7"),
        ("https://www.example.com/", "https://example.com/"),
        ("http://example.com:80/path", "http://example.com/path"),
        ("https://example.com/p?b=2&a=1", "https://example.com/p?a=1&b=2"),
        ("https://example.com/x#fragment", "https://example.com/x"),
    ],
)
def test_canonicalize_url(raw, expected):
    assert canonicalize_url(raw) == expected


def test_normalize_claim_text():
    a = normalize_claim_text("The  AIRSTRIKE  occurred!")
    b = normalize_claim_text("the airstrike occurred")
    assert a == b
    assert normalize_claim_text("cafés") == normalize_claim_text("cafes")
