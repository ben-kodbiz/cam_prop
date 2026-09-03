"""Analytics (agentodo §43, Phase 7).

Measures review coverage, correction speed, evidence depth and citation
completeness — never engagement, outrage or virality.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any


def _iso_days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat()


def _avg_review_age_days(conn: sqlite3.Connection) -> float | None:
    row = conn.execute(
        """SELECT AVG(julianday(coalesce(last_reviewed, updated_at))
                          - julianday(created_at)) AS avg_days
           FROM claims WHERE review_status = 'approved'"""
    ).fetchone()
    if row is None or row["avg_days"] is None:
        return None
    return round(float(row["avg_days"]), 2)


def _avg_evidence_per_claim(conn: sqlite3.Connection, *, approved_only: bool = True) -> float:
    cond = "WHERE review_status = 'approved'" if approved_only else ""
    row = conn.execute(
        f"""SELECT AVG(n) FROM (
                SELECT COUNT(ce.evidence_id) AS n
                FROM claims c
                LEFT JOIN claim_evidence ce ON ce.claim_id = c.id
                {cond}
                GROUP BY c.id
            )"""
    ).fetchone()
    if row is None or row[0] is None:
        return 0.0
    value: float = round(float(row[0]), 2)
    return value


def _correction_rate(conn: sqlite3.Connection) -> float:
    """Share of approved claims whose status changed after first setting."""
    row = conn.execute(
        """SELECT COUNT(*) AS corrections FROM audit_log
           WHERE action = 'status_change' AND entity_type = 'claim'"""
    ).fetchone()
    corrections = row["corrections"] if row else 0
    approved = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE review_status = 'approved'"
    ).fetchone()[0]
    if not approved:
        return 0.0
    rate: float = round(min(1.0, corrections / approved), 4)
    return rate


def _citation_completeness(conn: sqlite3.Connection) -> float:
    """Share of approved-claim evidence rows with excerpt or pointer."""
    row = conn.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN e.excerpt IS NOT NULL AND e.excerpt != ''
                            OR e.section IS NOT NULL
                            OR e.page_number IS NOT NULL THEN 1 ELSE 0 END) AS cited
           FROM claim_evidence ce
           JOIN evidence e ON e.id = ce.evidence_id
           JOIN claims c ON c.id = ce.claim_id
           WHERE c.review_status = 'approved'"""
    ).fetchone()
    if row is None or not row["total"]:
        return 0.0
    completeness: float = round(row["cited"] / row["total"], 4)
    return completeness


def compute_stats(conn: sqlite3.Connection, *, days: int = 30) -> dict[str, Any]:
    """All §43 metrics in one snapshot (used by CLI + site export)."""
    since = _iso_days_ago(days)
    approved_status_change = conn.execute(
        """SELECT COUNT(*) FROM audit_log
           WHERE action = 'status_change' AND entity_type = 'claim'
             AND ts >= ?""",
        (since,),
    ).fetchone()[0]
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "window_days": days,
        "claims": {
            "total": conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
            "by_status": {
                r["status"]: r["n"]
                for r in conn.execute(
                    "SELECT status, COUNT(*) AS n FROM claims GROUP BY status"
                ).fetchall()
            },
            "by_review": {
                r["review_status"]: r["n"]
                for r in conn.execute(
                    "SELECT review_status, COUNT(*) AS n FROM claims GROUP BY review_status"
                ).fetchall()
            },
            "by_topic": {
                r["topic"]: r["n"]
                for r in conn.execute(
                    "SELECT topic, COUNT(*) AS n FROM claims WHERE topic IS NOT NULL"
                    " GROUP BY topic ORDER BY n DESC LIMIT 20"
                ).fetchall()
            },
        },
        "sources": {
            "total": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "by_tier": {
                str(r["source_tier"]): r["n"]
                for r in conn.execute(
                    "SELECT source_tier, COUNT(*) AS n FROM sources GROUP BY source_tier"
                ).fetchall()
            },
            "books": conn.execute(
                "SELECT COUNT(*) FROM sources WHERE doc_kind = 'book'"
            ).fetchone()[0],
        },
        "evidence": {
            "total": conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
            "avg_per_approved_claim": _avg_evidence_per_claim(conn),
        },
        "quality": {
            "review_coverage": _review_coverage(conn),
            "avg_review_age_days": _avg_review_age_days(conn),
            "correction_rate": _correction_rate(conn),
            "citation_completeness": _citation_completeness(conn),
            "status_changes_last_window": approved_status_change,
        },
        "other": {
            "legal_documents": conn.execute("SELECT COUNT(*) FROM legal_documents").fetchone()[0],
            "corporate_relationships": conn.execute(
                "SELECT COUNT(*) FROM corporate_relationships"
            ).fetchone()[0],
            "alternatives": conn.execute("SELECT COUNT(*) FROM alternatives").fetchone()[0],
            "publications": conn.execute(
                "SELECT COUNT(*) FROM publications WHERE retracted_at IS NULL"
            ).fetchone()[0],
            "audit_entries": conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
        },
    }


def _review_coverage(conn: sqlite3.Connection) -> float:
    """Share of claims that have a completed review decision (any outcome)."""
    total = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    if not total:
        return 0.0
    reviewed = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE review_status IN ('approved', 'rejected')"
    ).fetchone()[0]
    coverage: float = round(reviewed / total, 4)
    return coverage
