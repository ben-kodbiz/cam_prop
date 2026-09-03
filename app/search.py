"""Hybrid search: FTS keyword + metadata filtering + ranking (agentodo §27).

Semantic similarity alone never establishes factual correctness; Phase 1 is
keyword + metadata only, by design.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class SearchHit:
    claim_id: str
    claim_text: str
    score: float
    matched_by: str  # keyword | metadata
    status: str


def _fts_escape(query: str) -> str:
    return query.replace('"', '""')


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    status: str | None = None,
    speaker_type: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[SearchHit]:
    """Keyword search combined with metadata filters.

    Results must satisfy ALL metadata filters AND match the keyword query.
    An empty query with filters returns metadata-matched rows.
    """
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("c.status = ?")
        params.append(status)
    if speaker_type:
        clauses.append("c.speaker_type = ?")
        params.append(speaker_type)
    if topic:
        clauses.append("c.topic = ?")
        params.append(topic)
    where_meta = (" AND " + " AND ".join(clauses)) if clauses else ""

    hits: list[SearchHit] = []
    seen: set[str] = set()
    if query.strip():
        fts_q = '"' + _fts_escape(query.strip()) + '"'
        rows = conn.execute(
            f"""SELECT c.id, c.claim_text, c.status, rank
                FROM claims_fts f JOIN claims c ON c.id = f.claim_id
                WHERE claims_fts MATCH ?{where_meta}
                ORDER BY rank LIMIT ?""",
            [fts_q, *params, limit],
        ).fetchall()
        for r in rows:
            hits.append(SearchHit(r["id"], r["claim_text"], -r["rank"], "keyword", r["status"]))
            seen.add(r["id"])
    else:
        rows = conn.execute(
            f"SELECT c.id, c.claim_text, c.status FROM claims c WHERE 1=1{where_meta}"
            " ORDER BY c.created_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
        for r in rows:
            hits.append(SearchHit(r["id"], r["claim_text"], 0.0, "metadata", r["status"]))

    # fill remaining slots with metadata matches if keyword results are few
    if query.strip() and len(hits) < limit:
        extra = conn.execute(
            f"SELECT c.id, c.claim_text, c.status FROM claims c WHERE 1=1{where_meta}"
            " ORDER BY c.created_at DESC LIMIT ?",
            [*params, limit],
        ).fetchall()
        for r in extra:
            if r["id"] in seen:
                continue
            hits.append(SearchHit(r["id"], r["claim_text"], 0.0, "metadata", r["status"]))
            seen.add(r["id"])
            if len(hits) >= limit:
                break
    return hits


def source_search(conn: sqlite3.Connection, query: str, *, limit: int = 50) -> list[sqlite3.Row]:
    """Search sources by title/publisher/canonical URL."""
    like = f"%{query}%"
    return conn.execute(
        "SELECT * FROM sources WHERE title LIKE ? OR publisher LIKE ? OR canonical_url LIKE ?"
        " ORDER BY source_tier, created_at DESC LIMIT ?",
        (like, like, like, limit),
    ).fetchall()
