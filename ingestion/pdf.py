"""PDF ingestion via PyMuPDF (optional dependency)."""

from __future__ import annotations

from types import ModuleType
from typing import cast

from ingestion.rss import fetch


class PdfIngestError(RuntimeError):
    pass


def _import_pymupdf() -> ModuleType:
    """Import PyMuPDF under either its new or legacy name."""
    try:
        import pymupdf

        return pymupdf
    except ImportError:
        import fitz  # type: ignore[import-untyped]  # PyMuPDF < 1.24

        return cast("ModuleType", fitz)


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
