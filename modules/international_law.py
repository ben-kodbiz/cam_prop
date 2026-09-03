"""International-law module (agentodo §11).

Every legal record must state what the finding DOES NOT establish.
Never conflate allegation, provisional measure, judgment, etc.
"""

from __future__ import annotations

import sqlite3

from app import audit
from app.constants import LEGAL_RECORD_TYPES


class LawError(ValueError):
    pass


def create_legal_record(
    conn: sqlite3.Connection,
    *,
    body: str,
    case_or_document: str,
    document_type: str,
    date: str,
    finding: str,
    does_not_establish: str,
    source_id: str,
    jurisdiction: str | None = None,
    actor: str = "system",
) -> str:
    """Create a legal-record claim+evidence pair.

    `document_type` must be one of LEGAL_RECORD_TYPES so that 'provisional
    measure' can never silently become 'judgment'.
    """
    if document_type not in LEGAL_RECORD_TYPES:
        msg = f"unknown document_type {document_type!r}; known: {LEGAL_RECORD_TYPES}"
        raise LawError(msg)
    if not does_not_establish.strip():
        msg = "does_not_establish is mandatory for legal records (agentodo §11)"
        raise LawError(msg)
    if not conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone():
        msg = f"source {source_id} does not exist"
        raise LawError(msg)

    from app.claims import create_claim
    from app.constants import ID_PREFIXES

    assert "claim" in ID_PREFIXES
    claim_id = create_claim(
        conn,
        claim_text=f"[{body} — {case_or_document}] {finding}",
        speaker=body,
        speaker_type="un_body" if body.startswith("UN") or body in ("ICJ", "ICC") else "government",
        source_id=source_id,
        published_at=date,
        topic="international_law",
        importance="high",
        actor=actor,
    )
    conn.execute(
        "UPDATE claims SET status = 'supported', review_status = 'pending',"
        " confidence = 0.9 WHERE id = ?",
        (claim_id,),
    )
    audit.log(
        conn,
        actor,
        "create",
        "legal_record",
        claim_id,
        {"body": body, "document_type": document_type},
    )
    return claim_id


def legal_records(conn: sqlite3.Connection, body: str | None = None) -> list[sqlite3.Row]:
    q = (
        "SELECT * FROM claims WHERE topic = 'international_law'"
        " AND claim_text LIKE ? ORDER BY published_at DESC"
    )
    return conn.execute(q, (f"[{body}%]%" if body else "%",)).fetchall()
