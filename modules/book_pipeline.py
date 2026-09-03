"""Book ingestion pipeline: import local PDF books as sources of truth.

Books are tier-3 sources. We store the file (hashed + archived), extract
per-page text so evidence can cite exact pages, and index the text for
keyword search. Copyright: we never republish the book; page numbers and
short excerpts (<= 500 chars) are the citable units.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from app.sources import create_book_source


class BookImportError(RuntimeError):
    pass


@dataclass
class BookImportResult:
    source_id: str
    title: str
    pages: int
    indexed_chars: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "pages": self.pages,
            "indexed_chars": self.indexed_chars,
        }


def import_book(
    conn: sqlite3.Connection,
    *,
    path: str | Path,
    title: str,
    author: str | None = None,
    publisher: str | None = None,
    year: str | None = None,
    isbn: str | None = None,
    language: str = "en",
    archive_dir: Path | None = None,
    extract_pages: bool = True,
) -> BookImportResult:
    """Import a PDF book: register source, extract page texts, index them.

    Page texts are stored in the book's archive folder as pages.json
    (one entry per page). This enables exact page citations in evidence
    records without keeping the whole text in the database.
    """
    file_path = Path(path)
    if not file_path.is_file():
        msg = f"book file not found: {file_path}"
        raise BookImportError(msg)
    data = file_path.read_bytes()

    # count/extract pages first so the source row knows its page range
    page_texts: list[str] = []
    if extract_pages:
        page_texts = extract_page_texts(data)
    pages = len(page_texts)

    sid = create_book_source(
        conn,
        path=file_path,
        title=title,
        author=author,
        publisher=publisher,
        year=year,
        isbn=isbn,
        language=language,
        content=data,
        book_pages=pages or None,
        archive_dir=archive_dir,
    )

    indexed_chars = 0
    if page_texts:
        indexed_chars = sum(len(t) for t in page_texts)
        if archive_dir is not None:
            _write_pages(archive_dir, sid, page_texts, title)

    return BookImportResult(
        source_id=sid,
        title=title,
        pages=pages,
        indexed_chars=indexed_chars,
    )


def extract_page_texts(pdf_bytes: bytes) -> list[str]:
    """Extract text per page via PyMuPDF (requires the [pdf] extra)."""
    try:
        from ingestion.pdf import _import_pymupdf

        pymupdf = _import_pymupdf()
    except ImportError as e:
        msg = "PyMuPDF is required for book ingestion: pip install -e '.[pdf]'"
        raise BookImportError(msg) from e
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        texts = [page.get_text() for page in doc]
        doc.close()
        return texts
    except Exception as e:
        msg = f"PDF parsing failed: {e}"
        raise BookImportError(msg) from e


def count_pdf_pages(pdf_bytes: bytes) -> int:
    try:
        return len(extract_page_texts(pdf_bytes))
    except BookImportError:
        return 0


def _write_pages(archive_dir: Path, sid: str, page_texts: list[str], title: str) -> None:
    dest = archive_dir / "books" / sid
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_id": sid,
        "title": title,
        "pages": [{"page": i + 1, "chars": len(t), "text": t} for i, t in enumerate(page_texts)],
    }
    (dest / "pages.json").write_text(
        json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_pages(archive_dir: Path, sid: str) -> dict[int, str]:
    """Load extracted page texts for a book source (page number -> text)."""
    path = archive_dir / "books" / sid / "pages.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {p["page"]: p["text"] for p in data.get("pages", [])}


def search_book(archive_dir: Path, sid: str, query: str) -> list[dict[str, object]]:
    """Keyword search inside an imported book; returns matching pages.

    This is evidence *discovery* — a match locates a page, it never
    establishes truth by itself.
    """
    pages = load_pages(archive_dir, sid)
    q = query.casefold()
    hits: list[dict[str, object]] = []
    for page_no in sorted(pages):
        text = pages[page_no]
        if q in text.casefold():
            idx = text.casefold().find(q)
            start = max(0, idx - 120)
            excerpt = text[start : idx + len(query) + 120].replace("\n", " ").strip()
            hits.append({"page": page_no, "excerpt": excerpt[:500]})
            if len(hits) >= 20:
                break
    return hits


def get_book_source(conn: sqlite3.Connection, source_id: str) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT * FROM sources WHERE id = ? AND doc_kind = 'book'", (source_id,)
    ).fetchone()
    return cast("sqlite3.Row | None", row)


def list_books(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sources WHERE doc_kind = 'book' ORDER BY created_at"
    ).fetchall()
