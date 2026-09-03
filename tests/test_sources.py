"""Source tests: registration, tier mapping, dedup, archiving, hash verify."""

from __future__ import annotations

import pytest
from app.sources import (
    DuplicateSourceError,
    create_source,
    find_by_url,
    get_source,
    verify_archive,
)


def _mk_source(conn, **kw):
    defaults = dict(
        url="https://example.org/article",
        title="Example article",
        source_type="news",
        content_text="body text",
    )
    defaults.update(kw)
    return create_source(conn, **defaults)


def test_create_source_assigns_tier(tmp_db):
    sid = _mk_source(tmp_db, source_type="icj")
    row = get_source(tmp_db, sid)
    assert row["source_tier"] == 1
    sid2 = _mk_source(tmp_db, url="https://example.org/2", source_type="news")
    assert get_source(tmp_db, sid2)["source_tier"] == 2


def test_unknown_source_type_rejected(tmp_db):
    with pytest.raises(ValueError, match="unknown source_type"):
        _mk_source(tmp_db, source_type="rumour")


def test_duplicate_url_rejected(tmp_db):
    _mk_source(tmp_db)
    with pytest.raises(DuplicateSourceError):
        _mk_source(tmp_db, url="https://example.org/article?utm_source=x")


def test_find_by_url_ignores_tracking(tmp_db):
    sid = _mk_source(tmp_db)
    row = find_by_url(tmp_db, "https://example.org/article?fbclid=abc")
    assert row and row["id"] == sid


def test_content_text_hashed(tmp_db):
    sid = _mk_source(tmp_db, content_text="exact body")
    from app.util import sha256_text

    assert get_source(tmp_db, sid)["content_hash"] == sha256_text("exact body")


def test_archive_written_and_verified(tmp_db, tmp_path):
    archive = tmp_path / "archive"
    sid = create_source(
        tmp_db,
        url="https://example.org/doc",
        title="Doc",
        source_type="government_document",
        content=b"raw document bytes",
        archive_dir=archive,
    )
    row = get_source(tmp_db, sid)
    assert row["archive_path"]
    base = archive / row["archive_path"]
    assert (base / "source.txt").read_bytes() == b"raw document bytes"
    assert (base / "metadata.json").is_file()
    assert (base / "sha256.txt").is_file()
    assert verify_archive(archive, row)

    # tamper -> verification fails
    (base / "source.txt").write_bytes(b"tampered")
    assert not verify_archive(archive, row)


def test_neither_content_nor_text_rejected(tmp_db):
    with pytest.raises(ValueError, match="required for hashing"):
        create_source(
            tmp_db,
            url="https://x.org",
            title="x",
            source_type="news",
            content=None,
            content_text=None,
        )
