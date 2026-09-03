"""Shared utilities: IDs, timestamps, hashing, URL canonicalization, normalization."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def next_id(conn: sqlite3.Connection, table: str, prefix: str, year: int | None = None) -> str:
    """Generate the next sequential ID like CLM-2026-0007.

    Scans existing IDs for the given prefix+year and returns max+1.
    """
    from app.constants import ID_PREFIXES

    if table not in ID_PREFIXES and prefix not in ID_PREFIXES.values():
        msg = f"unknown id prefix for table {table!r}"
        raise ValueError(msg)
    p = ID_PREFIXES.get(table, prefix)
    yr = year if year is not None else datetime.now(UTC).year
    stem = f"{p}-{yr}-"
    rows = conn.execute(f"SELECT id FROM {table} WHERE id LIKE ?", (stem + "%",)).fetchall()
    max_seq = 0
    for row in rows:
        try:
            seq = int(row["id"][len(stem) :])
        except ValueError:
            continue
        max_seq = max(max_seq, seq)
    return f"{stem}{max_seq + 1:04d}"


_TRACKING_RE = re.compile(
    r"^(utm_[a-z_]+|fbclid|gclid|mc_cid|mc_eid|ref|ref_src|source|igsh|si|si=.*|spm|ved)$"
)


def canonicalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    Lowercases scheme/host, strips default ports, tracking params, fragments,
    trailing slashes and www prefix.
    """
    url = url.strip()
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme.lower() or "https"
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _TRACKING_RE.match(k.lower())
    ]
    query.sort()
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    qs = urlencode(query)
    return urlunsplit((scheme, netloc, path, qs, ""))


def normalize_claim_text(text: str) -> str:
    """Lightweight normalization for duplicate detection.

    Unicode NFKC, casefold, strip punctuation/diacritics, collapse whitespace.
    Preserves meaning enough to catch near-duplicates.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()
