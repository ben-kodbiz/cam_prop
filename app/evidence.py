"""Evidence records, claim linking and multi-dimensional scoring (agentodo §6)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app import audit
from app.constants import EVIDENCE_DIMENSIONS
from app.util import next_id, utcnow_iso


class EvidenceError(ValueError):
    pass


def _validate_dimensions(dimensions: dict[str, Any]) -> dict[str, Any]:
    dims = {k: v for k, v in dimensions.items() if k in EVIDENCE_DIMENSIONS}
    for k, v in list(dims.items()):
        if k == "primary_source":
            if not isinstance(v, bool):
                msg = f"dimension {k} must be bool"
                raise EvidenceError(msg)
        else:
            if not isinstance(v, int | float) or not 0 <= float(v) <= 5:
                msg = f"dimension {k} must be number 0-5"
                raise EvidenceError(msg)
    return dims


def create_evidence(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    evidence_type: str = "document",
    excerpt: str | None = None,
    page_number: str | None = None,
    section: str | None = None,
    context: str | None = None,
    dimensions: dict[str, Any] | None = None,
    actor: str = "system",
    evidence_id: str | None = None,
) -> str:
    """Create an evidence record with validated scoring dimensions.

    Excerpts must be short (<= 500 chars) — never mirror copyrighted content.
    """
    source_row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if source_row is None:
        msg = f"source {source_id} does not exist"
        raise EvidenceError(msg)
    if excerpt is not None and len(excerpt) > 500:
        msg = "excerpt exceeds 500 characters; store a short quotation plus a pointer"
        raise EvidenceError(msg)
    if page_number is not None and source_row["doc_kind"] != "book":
        msg = "page_number is only valid for book sources; cite section/URL instead"
        raise EvidenceError(msg)
    if (
        page_number is not None
        and source_row["book_pages"] is not None
        and page_number.isdigit()
        and not 1 <= int(page_number) <= source_row["book_pages"]
    ):
        msg = f"page_number {page_number} outside book range 1-{source_row['book_pages']}"
        raise EvidenceError(msg)
    dims = _validate_dimensions(dimensions or {})

    now = utcnow_iso()
    eid = evidence_id or next_id(conn, "evidence", "EVD")
    strength = evidence_strength(dims)
    conn.execute(
        """INSERT INTO evidence (id, source_id, evidence_type, excerpt, page_number, section,
             context, dimensions_json, strength, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            eid,
            source_id,
            evidence_type,
            excerpt,
            page_number,
            section,
            context,
            json.dumps(dims, ensure_ascii=False, sort_keys=True),
            strength,
            now,
            now,
        ),
    )
    audit.log(
        conn,
        actor,
        "create",
        "evidence",
        eid,
        {"source_id": source_id, "evidence_type": evidence_type},
    )
    return eid


def link_evidence(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    evidence_id: str,
    relationship: str = "unspecified",
    actor: str = "system",
) -> None:
    """Link evidence to a claim. relationship: supports | contradicts | context."""
    if relationship not in ("supports", "contradicts", "context", "unspecified"):
        msg = f"unknown relationship {relationship!r}"
        raise EvidenceError(msg)
    for table, key, kind in (("claims", claim_id, "claim"), ("evidence", evidence_id, "evidence")):
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (key,)).fetchone():
            msg = f"{kind} {key} does not exist"
            raise EvidenceError(msg)
    # keep evidence.supports_claim consistent with the link relationship
    flag = 1 if relationship == "supports" else (0 if relationship == "contradicts" else None)
    conn.execute(
        "INSERT OR REPLACE INTO claim_evidence (claim_id, evidence_id, relationship, created_at)"
        " VALUES (?, ?, ?, ?)",
        (claim_id, evidence_id, relationship, utcnow_iso()),
    )
    if flag is not None:
        conn.execute(
            "UPDATE evidence SET supports_claim = ?, updated_at = ? WHERE id = ?",
            (flag, utcnow_iso(), evidence_id),
        )
    audit.log(
        conn,
        actor,
        "link",
        "claim_evidence",
        claim_id,
        {"evidence_id": evidence_id, "relationship": relationship},
    )


def get_evidence_for_claim(conn: sqlite3.Connection, claim_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT e.*, ce.relationship, s.source_tier, s.publisher, s.canonical_url, s.title,
                  s.published_at, s.archive_path, s.source_type
           FROM claim_evidence ce
           JOIN evidence e ON e.id = ce.evidence_id
           JOIN sources s ON s.id = e.source_id
           WHERE ce.claim_id = ?
           ORDER BY s.source_tier, e.created_at""",
        (claim_id,),
    ).fetchall()


def evidence_strength(score_dims: dict[str, Any]) -> float:
    """Compute a 0-1 strength from validated dimensions.

    Multi-dimensional by design — never a simplistic true/false score.
    Weights: source quality and primary-ness dominate; recency is minor.
    """

    def g(k: str) -> float:
        return float(score_dims.get(k, 0) or 0)

    quality = g("source_quality") / 5
    primary = 1.0 if score_dims.get("primary_source") else 0.4
    independence = g("independence") / 5
    directness = g("directness") / 5
    corroboration = g("corroboration") / 5
    contradiction = g("contradiction") / 5
    recency = g("recency") / 5
    base = (
        0.30 * quality
        + 0.25 * primary
        + 0.15 * independence
        + 0.15 * directness
        + 0.10 * corroboration
        + 0.05 * recency
    )
    return round(min(1.0, max(0.0, base)) * (1 - 0.5 * contradiction), 3)


def update_strengths(conn: sqlite3.Connection) -> int:
    """Recompute strength for all evidence rows from their dimensions."""
    n = 0
    for row in conn.execute("SELECT id, dimensions_json FROM evidence").fetchall():
        dims = json.loads(row["dimensions_json"] or "{}")
        conn.execute(
            "UPDATE evidence SET strength = ?, updated_at = ? WHERE id = ?",
            (evidence_strength(dims), utcnow_iso(), row["id"]),
        )
        n += 1
    return n


def strongest_evidence(
    conn: sqlite3.Connection, claim_id: str, relationship: str
) -> sqlite3.Row | None:
    rows = conn.execute(
        """SELECT e.* FROM claim_evidence ce JOIN evidence e ON e.id = ce.evidence_id
           WHERE ce.claim_id = ? AND ce.relationship = ?
           ORDER BY e.strength DESC LIMIT 1""",
        (claim_id, relationship),
    ).fetchall()
    return rows[0] if rows else None


def missing_evidence(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Summarize evidence gaps for the review queue."""
    dims_present: set[str] = set()
    supporting = contradicting = 0
    primary = False
    for row in get_evidence_for_claim(conn, claim_id):
        d = json.loads(row["dimensions_json"] or "{}")
        dims_present.update(d.keys())
        if row["relationship"] == "supports":
            supporting += 1
            primary = primary or bool(d.get("primary_source"))
        elif row["relationship"] == "contradicts":
            contradicting += 1
    return {
        "supporting": supporting,
        "contradicting": contradicting,
        "has_primary_support": primary,
        "missing": sorted(set(EVIDENCE_DIMENSIONS) - dims_present) if not primary else [],
    }
