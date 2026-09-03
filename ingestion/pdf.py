"""PDF ingestion via PyMuPDF (optional dependency)."""

from __future__ import annotations

from ingestion.rss import fetch


class PdfIngestError(RuntimeError):
    pass


def extract_pdf_text(content: bytes) -> str:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as e:
        msg = "PyMuPDF is required for PDF ingestion: pip install .[pdf]"
        raise PdfIngestError(msg) from e
    try:
        doc = fitz.open(stream=content, filetype="pdf")
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
