"""Corporate accountability module (agentodo §12-13).

Documents relationships with evidence; never starts from a predetermined
accusation, and never auto-classifies a commercial relationship as criminal.
"""

from __future__ import annotations

import json
import sqlite3

from app import audit
from app.util import next_id, utcnow_iso


class CorporateError(ValueError):
    pass


RELATIONSHIP_CLASSIFICATIONS = (
    "documented_contract",
    "documented_service",
    "reported_relationship",
    "company_denial",
    "company_confirmation",
    "disputed",
    "unknown",
    "ended",
    "ongoing",
)


def create_relationship(
    conn: sqlite3.Connection,
    *,
    company_org_id: str,
    service: str,
    customer: str,
    classification: str = "unknown",
    counterpart_org_id: str | None = None,
    contract_ref: str | None = None,
    contract_value: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    evidence_ids: list[str] | None = None,
    company_response: str | None = None,
    status_notes: str | None = None,
    confidence: float | None = None,
    actor: str = "system",
    relationship_id: str | None = None,
) -> str:
    """Create a corporate relationship record backed by evidence IDs."""
    if classification not in RELATIONSHIP_CLASSIFICATIONS:
        msg = f"unknown classification {classification!r}"
        raise CorporateError(msg)
    if not conn.execute("SELECT 1 FROM organizations WHERE id = ?", (company_org_id,)).fetchone():
        msg = f"company organization {company_org_id} does not exist"
        raise CorporateError(msg)
    for eid in evidence_ids or []:
        if not conn.execute("SELECT 1 FROM evidence WHERE id = ?", (eid,)).fetchone():
            msg = f"evidence {eid} does not exist"
            raise CorporateError(msg)

    now = utcnow_iso()
    rid = relationship_id or next_id(conn, "corporate_relationships", "CORP")
    conn.execute(
        """INSERT INTO corporate_relationships (id, company_org_id, counterpart_org_id,
             service, customer, contract_ref, contract_value, start_date, end_date,
             classification, evidence_ids_json, company_response, status_notes,
             confidence, review_status, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)""",
        (
            rid,
            company_org_id,
            counterpart_org_id,
            service,
            customer,
            contract_ref,
            contract_value,
            start_date,
            end_date,
            classification,
            json.dumps(evidence_ids or []),
            company_response,
            status_notes,
            confidence,
            now,
            now,
        ),
    )
    audit.log(
        conn,
        actor,
        "create",
        "relationship",
        rid,
        {"company": company_org_id, "service": service, "classification": classification},
    )
    return rid


def add_company_statement(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    statement_text: str,
    statement_type: str = "other",
    source_id: str | None = None,
    statement_date: str | None = None,
    relates_to_claim_id: str | None = None,
    relates_to_relationship_id: str | None = None,
    actor: str = "system",
    statement_id: str | None = None,
) -> str:
    """Record a company response — prevents one-sided documentation (§13)."""
    from app.constants import ID_PREFIXES as _P

    assert "statement" in _P
    if not conn.execute("SELECT 1 FROM organizations WHERE id = ?", (organization_id,)).fetchone():
        msg = f"organization {organization_id} does not exist"
        raise CorporateError(msg)
    now = utcnow_iso()
    sid = statement_id or next_id(conn, "company_statements", "CST")
    conn.execute(
        """INSERT INTO company_statements (id, organization_id, source_id, statement_text,
             statement_type, statement_date, relates_to_claim_id, relates_to_relationship_id,
             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sid,
            organization_id,
            source_id,
            statement_text,
            statement_type,
            statement_date,
            relates_to_claim_id,
            relates_to_relationship_id,
            now,
            now,
        ),
    )
    audit.log(
        conn,
        actor,
        "create",
        "statement",
        sid,
        {"organization_id": organization_id, "statement_type": statement_type},
    )
    return sid


def relationship_summary(conn: sqlite3.Connection, relationship_id: str) -> dict:
    """Answer the six accountability questions (§13) from the database."""
    row = conn.execute(
        """SELECT cr.*, o.name AS company_name, cp.name AS counterpart_name
           FROM corporate_relationships cr
           JOIN organizations o ON o.id = cr.company_org_id
           LEFT JOIN organizations cp ON cp.id = cr.counterpart_org_id
           WHERE cr.id = ?""",
        (relationship_id,),
    ).fetchone()
    if row is None:
        msg = f"relationship {relationship_id} does not exist"
        raise CorporateError(msg)
    evidence_rows = []
    for eid in json.loads(row["evidence_ids_json"] or "[]"):
        e = conn.execute(
            """SELECT e.*, s.publisher, s.title AS source_title, s.canonical_url
               FROM evidence e JOIN sources s ON s.id = e.source_id WHERE e.id = ?""",
            (eid,),
        ).fetchone()
        if e:
            evidence_rows.append(dict(e))
    statements = conn.execute(
        "SELECT * FROM company_statements WHERE relates_to_relationship_id = ?",
        (relationship_id,),
    ).fetchall()
    return {
        "relationship_id": row["id"],
        "company": row["company_name"],
        "counterpart": row["counterpart_name"],
        "service": row["service"],
        "customer": row["customer"],
        "what_is_documented": row["classification"],
        "evidence": evidence_rows,
        "company_response": [
            {"date": s["statement_date"], "type": s["statement_type"], "text": s["statement_text"]}
            for s in statements
        ],
        "unknowns": [k for k in ("contract_value", "start_date", "end_date") if not row[k]],
        "confidence": row["confidence"],
        "review_status": row["review_status"],
    }


def iter_relationships(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT cr.*, o.name AS company_name FROM corporate_relationships cr
           JOIN organizations o ON o.id = cr.company_org_id ORDER BY cr.created_at"""
    ).fetchall()
