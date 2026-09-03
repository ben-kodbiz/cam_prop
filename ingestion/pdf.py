"""PDF ingestion via PyMuPDF (optional dependency)."""

from __future__ import annotations

from types import ModuleType

from ingestion.rss import fetch


class PdfIngestError(RuntimeError):
    pass


def _import_pymupdf() -> ModuleType:
    """Import PyMuPDF under either its new or legacy name.

    Both import paths are typed via pyproject overrides when missing, so no
    inline ignores are needed in either environment.
    """
    try:
        import pymupdf

        return pymupdf  # type: ignore[no-any-return]
    except ImportError:
        import fitz  # PyMuPDF < 1.24 (untyped shim)

        return fitz  # type: ignore[no-any-return]


def extract_pdf_text(content: bytes) -> str:
    try:
        pymupdf = _import_pymupdf()
    except ImportError as e:
        msg = "PyMuPDF is required for PDF ingestion: pip install -e '.[pdf]'"
        raise PdfIngestError(msg) from e
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception as e:
        msg = f"PDF parsing failed: {e}"
        raise PdfIngestError(msg) from e


def ingest(url: str) -> tuple[str, bytes]:
    """Fetch a PDF, return (text, raw_bytes)."""
    resp = fetch(url)
    return extract_pdf_text(resp.content), resp.content


def extract_pdf_text_from_path(path: str) -> str:
    from pathlib import Path

    return extract_pdf_text(Path(path).read_bytes())
