"""Human review gate (agentodo §10). High-impact topics always require approval."""

from __future__ import annotations

import json
import sqlite3

from app import audit
from app.claims import ClaimError
from app.constants import HIGH_IMPACT_TOPICS
from app.util import next_id, utcnow_iso

REVIEW_CHECKLIST: tuple[str, ...] = (
    "original_claim_represented",
    "speaker_identified",
    "date_correct",
    "primary_source",
    "contradictory_evidence_searched",
    "fact_separated_from_interpretation",
    "allegation_distinguished_from_finding",
    "legal_terminology_accurate",
    "other_party_response_included",
    "citations_correct",
    "uncertainty_stated",
    "no_false_certainty",
)

# Legal records are always high-stakes: approving one requires these
# (agentodo §11 — never conflate record types, always state the negation).
LEGAL_CHECKLIST: tuple[str, ...] = (
    "body_and_case_correct",
    "document_type_correct",
    "date_correct",
    "finding_accurately_stated",
    "does_not_establish_stated",
    "source_is_primary",
    "citations_correct",
    "uncertainty_stated",
)


class ReviewError(ValueError):
    pass


def is_high_impact(claim_row: sqlite3.Row) -> bool:
    topic = (claim_row["topic"] or "").strip()
    return topic in HIGH_IMPACT_TOPICS


def requires_review(claim_row: sqlite3.Row) -> bool:
    """All claims require review before publication; high-impact ones cannot skip."""
    return True


def submit_review(
    conn: sqlite3.Connection,
    *,
    subject_type: str,
    subject_id: str,
    reviewer: str,
    decision: str,
    checklist: dict[str, bool] | None = None,
    notes: str | None = None,
) -> str:
    """Record a human review decision. High-impact claims need a full checklist."""
    if subject_type not in (
        "claim",
        "relationship",
        "statement",
        "alternative",
        "legal_document",
    ):
        msg = f"unknown subject_type {subject_type!r}"
        raise ReviewError(msg)
    if decision not in ("approve", "reject", "request_evidence"):
        msg = f"unknown decision {decision!r}"
        raise ReviewError(msg)
    if not reviewer.strip():
        msg = "reviewer name is required"
        raise ReviewError(msg)

    table = {
        "claim": "claims",
        "relationship": "corporate_relationships",
        "statement": "company_statements",
        "alternative": "alternatives",
        "legal_document": "legal_documents",
    }[subject_type]
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (subject_id,)).fetchone()
    if row is None:
        msg = f"{subject_type} {subject_id} does not exist"
        raise ReviewError(msg)

    cl = {k: bool(v) for k, v in (checklist or {}).items()}
    if subject_type == "claim" and is_high_impact(row) and decision == "approve":
        missing = [k for k in REVIEW_CHECKLIST if not cl.get(k)]
        if missing:
            msg = f"high-impact claim approval requires completed checklist; missing: {missing}"
            raise ReviewError(msg)
    if subject_type == "legal_document" and decision == "approve":
        missing = [k for k in LEGAL_CHECKLIST if not cl.get(k)]
        if missing:
            msg = f"legal-document approval requires completed checklist; missing: {missing}"
            raise ReviewError(msg)

    now = utcnow_iso()
    rid = next_id(conn, "reviews", "REV")
    conn.execute(
        """INSERT INTO reviews (id, subject_type, subject_id, reviewer, decision,
             checklist_json, notes, reviewed_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rid,
            subject_type,
            subject_id,
            reviewer,
            decision,
            json.dumps(cl, ensure_ascii=False, sort_keys=True),
            notes,
            now,
            now,
        ),
    )

    new_status = {"approve": "approved", "reject": "rejected", "request_evidence": "pending"}[
        decision
    ]
    status_col = {
        "claims": ("review_status", "last_reviewed"),
        "corporate_relationships": ("review_status", "last_reviewed"),
        "company_statements": None,
        "alternatives": ("review_status", None),
        "legal_documents": ("review_status", "last_reviewed"),
    }[table]
    if status_col is not None:
        review_col, reviewed_col = status_col
        if reviewed_col:
            conn.execute(
                f"UPDATE {table} SET {review_col} = ?, {reviewed_col} = ?,"
                " revision = revision + 1 WHERE id = ?",
                (new_status, now, subject_id),
            )
        else:
            conn.execute(
                f"UPDATE {table} SET {review_col} = ?, revision = revision + 1 WHERE id = ?",
                (new_status, subject_id),
            )
    audit.log(
        conn,
        reviewer,
        decision,
        subject_type,
        subject_id,
        {"decision": decision, "checklist": cl},
        notes,
    )
    return rid


def review_history(
    conn: sqlite3.Connection, subject_type: str, subject_id: str
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM reviews WHERE subject_type = ? AND subject_id = ? ORDER BY reviewed_at DESC",
        (subject_type, subject_id),
    ).fetchall()


def record_publication(
    conn: sqlite3.Connection,
    *,
    subject_type: str,
    subject_id: str,
    format: str,
    actor: str = "system",
) -> str:
    """Mark a reviewed subject as published. Enforces approval-first."""
    table = {
        "claim": "claims",
        "relationship": "corporate_relationships",
        "alternative": "alternatives",
        "legal_document": "legal_documents",
    }[subject_type]
    row = conn.execute(f"SELECT review_status FROM {table} WHERE id = ?", (subject_id,)).fetchone()
    if row is None:
        msg = f"{subject_type} {subject_id} does not exist"
        raise ReviewError(msg)
    if row["review_status"] != "approved":
        msg = (
            f"cannot publish {subject_id}: review_status is"
            f" {row['review_status']!r}, not 'approved'"
        )
        raise ReviewError(msg)
    from app.util import sha256_text

    now = utcnow_iso()
    pid = next_id(conn, "publications", "PUB")
    conn.execute(
        """INSERT INTO publications (id, subject_type, subject_id, format, published_at,
             content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(subject_type, subject_id, format) DO UPDATE SET
             published_at = excluded.published_at,
             content_hash = excluded.content_hash""",
        (
            pid,
            subject_type,
            subject_id,
            format,
            now,
            sha256_text(f"{subject_type}:{subject_id}:{format}@{now}"),
            now,
        ),
    )
    audit.log(conn, actor, "publish", subject_type, subject_id, {"format": format})
    return pid


def publish_guard(claim_row: sqlite3.Row) -> None:
    """Raise if a claim must not be auto-published (high-impact → human only)."""
    if claim_row["review_status"] != "approved":
        msg = "claim not approved for publication"
        raise ReviewError(msg)
    if is_high_impact(claim_row) and not claim_row["reviewer"]:
        raise ClaimError("high-impact claim requires a named human reviewer")
