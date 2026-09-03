"""Citation generation: every assessment cites primary sources (agentodo §53)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.util import canonicalize_url


@dataclass
class Citation:
    source_id: str
    title: str
    publisher: str | None
    url: str
    published_at: str | None
    retrieved_at: str | None
    archive_path: str | None
    source_tier: int
    excerpt: str | None

    def format(self) -> str:
        parts = [self.publisher or "Unknown publisher", f"“{self.title}”"]
        if self.published_at:
            parts.append(self.published_at)
        cite = ", ".join(parts) + f". [{self.source_id}] {self.url}"
        if self.excerpt:
            cite += f" — “{self.excerpt}”"
        return cite


def citation_for_source(conn: sqlite3.Connection, source_id: str) -> Citation | None:
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        return None
    return Citation(
        source_id=row["id"],
        title=row["title"],
        publisher=row["publisher"],
        url=row["url"],
        published_at=row["published_at"],
        retrieved_at=row["retrieved_at"],
        archive_path=row["archive_path"],
        source_tier=row["source_tier"],
        excerpt=None,
    )


def citations_for_claim(conn: sqlite3.Connection, claim_id: str) -> list[Citation]:
    """Citations for all evidence linked to a claim, tier-1 first."""
    rows = conn.execute(
        """SELECT s.*, e.excerpt FROM claim_evidence ce
           JOIN evidence e ON e.id = ce.evidence_id
           JOIN sources s ON s.id = e.source_id
           WHERE ce.claim_id = ?
           ORDER BY s.source_tier ASC, s.published_at DESC""",
        (claim_id,),
    ).fetchall()
    out = []
    for row in rows:
        out.append(
            Citation(
                source_id=row["id"],
                title=row["title"],
                publisher=row["publisher"],
                url=canonicalize_url(row["url"]),
                published_at=row["published_at"],
                retrieved_at=row["retrieved_at"],
                archive_path=row["archive_path"],
                source_tier=row["source_tier"],
                excerpt=row["excerpt"],
            )
        )
    return out


def claim_reference(claim_id: str) -> str:
    """Stable URL path for a claim (/claim/CLM-YYYY-NNNN/)."""
    return f"/claim/{claim_id}/"


def source_reference(source_id: str) -> str:
    return f"/source/{source_id}/"


def reproducibility_bundle(conn: sqlite3.Connection, claim_id: str) -> dict[str, object]:
    """Everything a third party needs to reproduce an assessment (agentodo §53)."""
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        msg = f"claim {claim_id} does not exist"
        raise ValueError(msg)
    citations = citations_for_claim(conn, claim_id)
    return {
        "claim_id": claim_id,
        "claim_text": claim["claim_text"],
        "speaker": claim["speaker"],
        "assessment": claim["status"],
        "confidence": claim["confidence"],
        "methodology_version": "open-evidence/0.1",
        "review_date": claim["last_reviewed"],
        "revision": claim["revision"],
        "citations": [
            {
                "source_id": c.source_id,
                "title": c.title,
                "publisher": c.publisher,
                "url": c.url,
                "published_at": c.published_at,
                "retrieved_at": c.retrieved_at,
                "archive_path": c.archive_path,
                "excerpt": c.excerpt,
            }
            for c in citations
        ],
    }
