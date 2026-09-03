"""Book pipeline tests: import, page extraction, page-cited evidence."""

from __future__ import annotations

import pytest

pymupdf = pytest.importorskip("pymupdf")

from app.claims import create_claim, set_status  # noqa: E402
from app.evidence import EvidenceError, create_evidence, link_evidence  # noqa: E402
from app.review import submit_review  # noqa: E402
from app.sources import DuplicateSourceError  # noqa: E402
from modules.book_pipeline import (  # noqa: E402
    BookImportError,
    get_book_source,
    import_book,
    list_books,
    load_pages,
    search_book,
)


def _make_pdf(tmp_path, pages: dict[int, str]) -> bytes:
    """Build a real multi-page PDF with the given page texts."""
    doc = pymupdf.open()
    for page_no in sorted(pages):
        page = doc.new_page()
        page.insert_text((72, 72), pages[page_no], fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture()
def book_pdf(tmp_path):
    data = _make_pdf(
        tmp_path,
        {
            1: "Introduction to evidence standards",
            2: "The court indicated provisional measures on page two",
            3: "Conclusion and sources",
        },
    )
    path = tmp_path / "evidence-book.pdf"
    path.write_bytes(data)
    return path


def test_import_book_registers_source(tmp_db, tmp_path, book_pdf):
    result = import_book(
        tmp_db,
        path=book_pdf,
        title="Evidence Handbook",
        author="A. Author",
        publisher="Press",
        year="2020",
        isbn="978-0-00-000000-0",
        archive_dir=tmp_path / "archive",
    )
    assert result.source_id.startswith("SRC-")
    assert result.pages == 3
    row = get_book_source(tmp_db, result.source_id)
    assert row is not None
    assert row["doc_kind"] == "book"
    assert row["source_tier"] == 3
    assert row["book_author"] == "A. Author"
    assert row["book_isbn"] == "978-0-00-000000-0"
    assert row["book_pages"] == 3
    assert row["local_path"].endswith("evidence-book.pdf")


def test_import_book_dedupes_by_hash(tmp_db, tmp_path, book_pdf):
    import_book(tmp_db, path=book_pdf, title="One", archive_dir=tmp_path / "archive")
    with pytest.raises(DuplicateSourceError):
        import_book(tmp_db, path=book_pdf, title="Two", archive_dir=tmp_path / "archive")


def test_import_book_archives_pdf_and_pages(tmp_db, tmp_path, book_pdf):
    result = import_book(
        tmp_db, path=book_pdf, title="Evidence Handbook", archive_dir=tmp_path / "archive"
    )
    base = tmp_path / "archive" / "books" / result.source_id
    assert (base / "book.pdf").is_file()
    assert (base / "sha256.txt").is_file()
    assert (base / "pages.json").is_file()
    pages = load_pages(tmp_path / "archive", result.source_id)
    assert sorted(pages) == [1, 2, 3]
    assert "provisional measures" in pages[2]


def test_import_book_missing_file(tmp_db, tmp_path):
    with pytest.raises((ValueError, BookImportError), match="not found"):
        import_book(tmp_db, path=tmp_path / "nope.pdf", title="X")


def test_search_book_finds_page(tmp_db, tmp_path, book_pdf):
    result = import_book(
        tmp_db, path=book_pdf, title="Evidence Handbook", archive_dir=tmp_path / "archive"
    )
    hits = search_book(tmp_path / "archive", result.source_id, "provisional measures")
    assert len(hits) == 1
    assert hits[0]["page"] == 2
    assert "provisional" in str(hits[0]["excerpt"])
    assert search_book(tmp_path / "archive", result.source_id, "zebra") == []


def test_page_cited_evidence(tmp_db, tmp_path, book_pdf):
    result = import_book(
        tmp_db, path=book_pdf, title="Evidence Handbook", archive_dir=tmp_path / "archive"
    )
    src = result.source_id
    cid = create_claim(
        tmp_db,
        claim_text="The handbook covers provisional measures.",
        speaker="Researcher",
        source_id=src,
    )
    ev = create_evidence(
        tmp_db,
        source_id=src,
        evidence_type="quotation",
        excerpt="The court indicated provisional measures on page two",
        page_number="2",
        context="Handbook discussion of court orders.",
        dimensions={"source_quality": 3, "primary_source": True, "directness": 4},
    )
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship="supports")
    submit_review(
        tmp_db, subject_type="claim", subject_id=cid, reviewer="r", decision="approve", checklist={}
    )
    set_status(tmp_db, cid, "supported", actor="r", override=True)

    row = tmp_db.execute("SELECT page_number, excerpt FROM evidence WHERE id = ?", (ev,)).fetchone()
    assert row["page_number"] == "2"


def test_page_number_rejected_for_url_sources(tmp_db, tmp_path):
    from app.sources import create_source

    sid = create_source(
        tmp_db,
        url="https://example.org/article",
        title="Article",
        source_type="news",
        content_text="x",
    )
    with pytest.raises(EvidenceError, match="book sources"):
        create_evidence(tmp_db, source_id=sid, page_number="5")


def test_page_number_out_of_range(tmp_db, tmp_path, book_pdf):
    result = import_book(tmp_db, path=book_pdf, title="Handbook", archive_dir=tmp_path / "archive")
    with pytest.raises(EvidenceError, match="outside book range"):
        create_evidence(tmp_db, source_id=result.source_id, page_number="99")
    with pytest.raises(EvidenceError, match="outside book range"):
        create_evidence(tmp_db, source_id=result.source_id, page_number="0")


def test_list_books(tmp_db, tmp_path, book_pdf):
    import_book(tmp_db, path=book_pdf, title="Handbook", archive_dir=tmp_path / "archive")
    books = list_books(tmp_db)
    assert len(books) == 1
    assert books[0]["doc_kind"] == "book"


def test_extract_invalid_pdf(tmp_db, tmp_path):
    with pytest.raises(BookImportError):
        # valid enough to register, but pages extraction will fail on garbage
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"%PDF-1.4 this is not a real pdf")
        import_book(tmp_db, path=bad, title="Bad", archive_dir=tmp_path / "archive")


def test_no_pages_flag_skips_extraction(tmp_db, tmp_path, book_pdf):
    result = import_book(
        tmp_db,
        path=book_pdf,
        title="Handbook",
        archive_dir=tmp_path / "archive",
        extract_pages=False,
    )
    assert result.indexed_chars == 0
    assert (tmp_path / "archive" / "books" / result.source_id / "pages.json").exists() is False
