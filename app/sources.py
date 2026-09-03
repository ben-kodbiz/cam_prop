"""Source ingestion records: registration, archiving, deduplication."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from app.constants import SOURCE_TIERS
from app.util import canonicalize_url, next_id, sha256_bytes, sha256_text, utcnow_iso


def create_source(
    conn: sqlite3.Connection,
    *,
    url: str,
    title: str,
    source_type: str,
    publisher: str | None = None,
    author: str | None = None,
    published_at: str | None = None,
    language: str = "en",
    content: bytes | None = None,
    content_text: str | None = None,
    archive_dir: Path | None = None,
    source_id: str | None = None,
    reliability_notes: str | None = None,
) -> str:
    """Register a web source. Content is hashed; optional local archive is created.

    Returns the source ID. Raises ValueError on duplicates or unknown type.
    """
    if source_type not in SOURCE_TIERS:
        msg = f"unknown source_type {source_type!r}; known: {sorted(SOURCE_TIERS)}"
        raise ValueError(msg)
    if source_type == "book":
        msg = "use create_book_source() for books (local PDF files)"
        raise ValueError(msg)
    tier = SOURCE_TIERS[source_type]
    canonical = canonicalize_url(url)
    existing = conn.execute(
        "SELECT id FROM sources WHERE canonical_url = ?", (canonical,)
    ).fetchone()
    if existing:
        msg = f"duplicate source: {canonical} already registered as {existing['id']}"
        raise DuplicateSourceError(msg, existing["id"])

    if content is not None:
        content_hash = sha256_bytes(content)
    elif content_text is not None:
        content_hash = sha256_text(content_text)
    else:
        msg = "either content (bytes) or content_text (str) is required for hashing"
        raise ValueError(msg)

    now = utcnow_iso()
    sid = source_id or next_id(conn, "sources", "SRC")
    archive_path: str | None = None
    if content is not None and archive_dir is not None:
        archive_path = _write_archive(archive_dir, sid, url, title, content, content_hash, now)

    conn.execute(
        """INSERT INTO sources (id, url, canonical_url, title, publisher, author,
             published_at, retrieved_at, source_type, source_tier, language,
             content_hash, archive_path, doc_kind, reliability_notes,
             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'url', ?, ?, ?)""",
        (
            sid,
            url,
            canonical,
            title,
            publisher,
            author,
            published_at,
            now,
            source_type,
            tier,
            language,
            content_hash,
            archive_path,
            reliability_notes,
            now,
            now,
        ),
    )
    return sid


def create_book_source(
    conn: sqlite3.Connection,
    *,
    path: str | Path,
    title: str,
    author: str | None = None,
    publisher: str | None = None,
    year: str | None = None,
    isbn: str | None = None,
    language: str = "en",
    content: bytes | None = None,
    book_pages: int | None = None,
    source_id: str | None = None,
    reliability_notes: str | None = None,
    archive_dir: Path | None = None,
) -> str:
    """Register a book as a local PDF source of truth.

    The PDF is hashed and optionally copied into the archive so evidence
    integrity can be verified later. Books are tier 3 (specialist) sources;
    they are primary for what the book itself says, not for world facts.
    """
    file_path = Path(path).resolve()
    if not file_path.is_file():
        msg = f"book file not found: {file_path}"
        raise ValueError(msg)
    data = content if content is not None else file_path.read_bytes()
    content_hash = sha256_bytes(data)

    # dedupe by content hash: same PDF file never registered twice
    existing = conn.execute(
        "SELECT id FROM sources WHERE content_hash = ? AND doc_kind = 'book'",
        (content_hash,),
    ).fetchone()
    if existing:
        msg = f"duplicate book: identical file already registered as {existing['id']}"
        raise DuplicateSourceError(msg, existing["id"])

    now = utcnow_iso()
    sid = source_id or next_id(conn, "sources", "SRC")
    local_path = str(file_path)
    archive_path: str | None = None
    if archive_dir is not None:
        rel = Path("books") / f"{sid}"
        dest = archive_dir / rel
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "book.pdf").write_bytes(data)
        (dest / "sha256.txt").write_text(content_hash + "\n", encoding="utf-8")
        (dest / "metadata.json").write_text(
            json.dumps(
                {
                    "id": sid,
                    "title": title,
                    "author": author,
                    "isbn": isbn,
                    "pages": book_pages,
                    "sha256": content_hash,
                    "imported_at": now,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        archive_path = str(rel)

    # synthetic canonical URL for books: book://<isbn|slug>
    slug = isbn or Path(title).as_posix().replace(" ", "-")[:60]
    canonical = f"book://{slug}"
    conn.execute(
        """INSERT INTO sources (id, url, canonical_url, title, publisher, author,
             published_at, retrieved_at, source_type, source_tier, language,
             content_hash, archive_path, local_path, doc_kind, book_author,
             book_isbn, book_publisher, book_year, book_pages, reliability_notes,
             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'book', 3, ?, ?, ?, ?, 'book',
                   ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sid,
            canonical,
            canonical,
            title,
            publisher,
            author,
            year,
            now,
            language,
            content_hash,
            archive_path,
            local_path,
            author,
            isbn,
            publisher,
            year,
            book_pages,
            reliability_notes,
            now,
            now,
        ),
    )
    return sid


class DuplicateSourceError(ValueError):
    def __init__(self, message: str, existing_id: str) -> None:
        super().__init__(message)
        self.existing_id = existing_id


def _write_archive(
    archive_dir: Path,
    sid: str,
    url: str,
    title: str,
    content: bytes,
    content_hash: str,
    retrieved_at: str,
) -> str:
    """Store archive/YYYY/MM/source-id/{metadata.json, source.txt, sha256.txt}."""
    from datetime import UTC, datetime

    dt = (
        datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        if retrieved_at
        else datetime.now(UTC)
    )
    rel = Path(str(dt.year)) / f"{dt.month:02d}" / sid
    dest = archive_dir / rel
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "source.txt").write_bytes(content)
    (dest / "sha256.txt").write_text(content_hash + "\n", encoding="utf-8")
    metadata = {
        "id": sid,
        "url": url,
        "title": title,
        "retrieved_at": retrieved_at,
        "sha256": content_hash,
    }
    (dest / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return str(rel)


def get_source(conn: sqlite3.Connection, source_id: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    return cast("sqlite3.Row | None", row)


def find_by_url(conn: sqlite3.Connection, url: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM sources WHERE canonical_url = ?", (canonicalize_url(url),)
    ).fetchone()
    return cast("sqlite3.Row | None", row)


def verify_archive(archive_dir: Path, source_row: sqlite3.Row) -> bool:
    """Re-hash archived content to prove evidence integrity (agentodo §23)."""
    if source_row["doc_kind"] == "book":
        base = archive_dir / source_row["archive_path"] if source_row["archive_path"] else None
        path = (base / "book.pdf") if base else None
        if path is None or not path.is_file():
            # fall back to the registered local file
            local = source_row["local_path"]
            path = Path(local) if local else None
        if path is None or not path.is_file():
            return False
        result: bool = sha256_bytes(path.read_bytes()) == source_row["content_hash"]
        return result
    if not source_row["archive_path"]:
        return False
    path = archive_dir / source_row["archive_path"] / "source.txt"
    if not path.is_file():
        return False
    result = sha256_bytes(path.read_bytes()) == source_row["content_hash"]
    return result


def verify_local_book(source_row: sqlite3.Row) -> bool:
    """Verify a book source against its registered local file."""
    local = source_row["local_path"]
    if not local:
        return False
    path = Path(local)
    if not path.is_file():
        return False
    result: bool = sha256_bytes(path.read_bytes()) == source_row["content_hash"]
    return result
