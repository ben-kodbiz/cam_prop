"""International-law module (agentodo §11, Phase 4).

Tracks ICJ/ICC/UN documents as structured records. Every record must state
what the finding DOES NOT establish; record types (allegation, provisional
measure, judgment, …) are never conflated. Records cross-link to claims so
a claim page can show the exact legal basis behind its assessment.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from app import audit
from app.constants import LEGAL_BODIES, LEGAL_RECORD_TYPES
from app.util import next_id, utcnow_iso


class LawError(ValueError):
    pass


def create_legal_document(
    conn: sqlite3.Connection,
    *,
    body: str,
    case_or_document: str,
    document_type: str,
    finding: str,
    does_not_establish: str,
    source_id: str,
    jurisdiction: str | None = None,
    doc_date: str | None = None,
    actor: str = "system",
    document_id: str | None = None,
) -> str:
    """Create a legal-record document.

    `document_type` must be one of LEGAL_RECORD_TYPES so that 'provisional
    measure' can never silently become 'judgment'. `does_not_establish` is
    mandatory: a record without its negation is incomplete and rejected.
    """
    if body not in LEGAL_BODIES:
        msg = f"unknown body {body!r}; known: {LEGAL_BODIES}"
        raise LawError(msg)
    if document_type not in LEGAL_RECORD_TYPES:
        msg = f"unknown document_type {document_type!r}; known: {LEGAL_RECORD_TYPES}"
        raise LawError(msg)
    if not does_not_establish.strip():
        msg = "does_not_establish is mandatory for legal records (agentodo §11)"
        raise LawError(msg)
    if not finding.strip():
        msg = "finding is mandatory for legal records"
        raise LawError(msg)
    if not conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone():
        msg = f"source {source_id} does not exist"
        raise LawError(msg)

    now = utcnow_iso()
    lid = document_id or next_id(conn, "legal_documents", "LGL")
    conn.execute(
        """INSERT INTO legal_documents (id, body, case_or_document, document_type,
             jurisdiction, doc_date, finding, does_not_establish, source_id,
             review_status, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)""",
        (
            lid,
            body,
            case_or_document,
            document_type,
            jurisdiction,
            doc_date,
            finding,
            does_not_establish,
            source_id,
            now,
            now,
        ),
    )
    audit.log(
        conn, actor, "create", "legal_document", lid, {"body": body, "document_type": document_type}
    )
    return lid


def link_claim(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    legal_document_id: str,
    actor: str = "system",
) -> None:
    """Cross-link a claim to a legal document (claim ↔ legal document ↔ evidence)."""
    for table, key, kind in (
        ("claims", claim_id, "claim"),
        ("legal_documents", legal_document_id, "legal document"),
    ):
        if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (key,)).fetchone():
            msg = f"{kind} {key} does not exist"
            raise LawError(msg)
    conn.execute(
        "INSERT OR IGNORE INTO claim_legal_documents (claim_id, legal_document_id,"
        " created_at) VALUES (?, ?, ?)",
        (claim_id, legal_document_id, utcnow_iso()),
    )
    audit.log(
        conn,
        actor,
        "link",
        "claim_legal_documents",
        claim_id,
        {"legal_document_id": legal_document_id},
    )


def get_document(conn: sqlite3.Connection, document_id: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM legal_documents WHERE id = ?", (document_id,)).fetchone()
    return cast("sqlite3.Row | None", row)


def documents_for_claim(conn: sqlite3.Connection, claim_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT ld.*, s.canonical_url, s.title AS source_title
           FROM claim_legal_documents cld
           JOIN legal_documents ld ON ld.id = cld.legal_document_id
           LEFT JOIN sources s ON s.id = ld.source_id
           WHERE cld.claim_id = ?
           ORDER BY ld.doc_date DESC""",
        (claim_id,),
    ).fetchall()


def claims_for_document(conn: sqlite3.Connection, document_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT c.* FROM claim_legal_documents cld
           JOIN claims c ON c.id = cld.claim_id
           WHERE cld.legal_document_id = ?
           ORDER BY c.discovered_at DESC""",
        (document_id,),
    ).fetchall()


def iter_documents(
    conn: sqlite3.Connection,
    *,
    body: str | None = None,
    approved_only: bool = False,
) -> list[sqlite3.Row]:
    q = "SELECT * FROM legal_documents WHERE 1=1"
    params: list[object] = []
    if body:
        q += " AND body = ?"
        params.append(body)
    if approved_only:
        q += " AND review_status = 'approved'"
    q += " ORDER BY doc_date DESC, id"
    rows = conn.execute(q, params).fetchall()
    return [cast("sqlite3.Row", r) for r in rows]


def document_summary(row: sqlite3.Row) -> dict[str, object]:
    """Flattened view for export/UI: finding + negation side by side."""
    return {
        "id": row["id"],
        "body": row["body"],
        "case_or_document": row["case_or_document"],
        "document_type": row["document_type"],
        "jurisdiction": row["jurisdiction"],
        "date": row["doc_date"],
        "finding": row["finding"],
        "does_not_establish": row["does_not_establish"],
        "source_id": row["source_id"],
        "review_status": row["review_status"],
        "last_reviewed": row["last_reviewed"],
        "revision": row["revision"],
    }
