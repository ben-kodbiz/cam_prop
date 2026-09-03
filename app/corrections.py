"""Corrections, clarifications and retractions (agentodo §21, Phase 7).

Every published record keeps its history: a correction creates a new
revision + audit entry; it never silently rewrites the past. Retracted
publications stay visible as retracted.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from app import audit
from app.claims import set_status
from app.util import utcnow_iso


class CorrectionError(ValueError):
    pass


CORRECTION_KINDS: tuple[str, ...] = (
    "correction",
    "clarification",
    "evidence_update",
    "status_change",
    "source_removal",
)


def correct_claim(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    kind: str,
    reason: str,
    reviewer: str,
    new_status: str | None = None,
    new_explanation: str | None = None,
) -> int:
    """Apply a tracked correction to a published claim.

    The claim's revision counter increments and the audit log records the
    correction with its reason — history remains reproducible.
    """
    if kind not in CORRECTION_KINDS:
        msg = f"unknown correction kind {kind!r}; known: {CORRECTION_KINDS}"
        raise CorrectionError(msg)
    if not reason.strip():
        msg = "a correction reason is mandatory (never silently rewrite history)"
        raise CorrectionError(msg)
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        msg = f"claim {claim_id} does not exist"
        raise CorrectionError(msg)
    if row["review_status"] != "approved":
        msg = f"claim {claim_id} is not approved; corrections apply to published records"
        raise CorrectionError(msg)

    if new_status is not None:
        set_status(conn, claim_id, new_status, actor=reviewer, override=True, reason=reason)
    if new_explanation is not None:
        conn.execute(
            "UPDATE claims SET explanation = ?, updated_at = ? WHERE id = ?",
            (new_explanation, utcnow_iso(), claim_id),
        )
    conn.execute(
        "UPDATE claims SET revision = revision + 1, updated_at = ? WHERE id = ?",
        (utcnow_iso(), claim_id),
    )
    audit.log(
        conn,
        reviewer,
        "correction",
        "claim",
        claim_id,
        {"kind": kind, "new_status": new_status},
        reason,
    )
    revision = conn.execute("SELECT revision FROM claims WHERE id = ?", (claim_id,)).fetchone()[
        "revision"
    ]
    return int(revision)


def retract_publication(
    conn: sqlite3.Connection,
    *,
    subject_type: str,
    subject_id: str,
    actor: str,
    reason: str,
) -> int:
    """Mark all live publications of a subject as retracted (kept visible)."""
    if not reason.strip():
        msg = "a retraction reason is mandatory"
        raise CorrectionError(msg)
    live = conn.execute(
        "SELECT COUNT(*) FROM publications WHERE subject_type = ? AND subject_id = ?"
        " AND retracted_at IS NULL",
        (subject_type, subject_id),
    ).fetchone()[0]
    if not live:
        msg = f"no live publication for {subject_type} {subject_id}"
        raise CorrectionError(msg)
    now = utcnow_iso()
    cur = conn.execute(
        "UPDATE publications SET retracted_at = ? WHERE subject_type = ?"
        " AND subject_id = ? AND retracted_at IS NULL",
        (now, subject_type, subject_id),
    )
    audit.log(conn, actor, "retract", subject_type, subject_id, {"retracted_at": now}, reason)
    return int(cur.rowcount or 0)


def correction_history(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
) -> list[sqlite3.Row]:
    """Corrections + retractions for one entity, oldest first."""
    rows = conn.execute(
        """SELECT * FROM audit_log
           WHERE entity_type = ? AND entity_id = ?
             AND action IN ('correction', 'retract', 'status_change')
           ORDER BY id ASC""",
        (entity_type, entity_id),
    ).fetchall()
    return [cast("sqlite3.Row", r) for r in rows]
