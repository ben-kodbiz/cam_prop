"""Reports (agentodo §7, Phase 7): weekly digest and corporate monthly.

Reports are generated only from approved evidence and always cite
claim IDs. They are text artifacts; publishing them is a human decision.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import cast

from app.evidence import get_evidence_for_claim

from publishing.generators import short_post


def _since(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat()


def weekly_report(conn: sqlite3.Connection, *, days: int = 7) -> str:
    """Digest of claims reviewed in the window: new, by status, corrections."""
    since = _since(days)
    new_claims = conn.execute(
        "SELECT * FROM claims WHERE discovered_at >= ? ORDER BY discovered_at DESC",
        (since,),
    ).fetchall()
    reviewed_claims = conn.execute(
        "SELECT * FROM claims WHERE last_reviewed >= ? AND review_status = 'approved'"
        " ORDER BY last_reviewed DESC",
        (since,),
    ).fetchall()
    corrections = conn.execute(
        """SELECT entity_id, details_json, reason FROM audit_log
           WHERE action = 'correction' AND ts >= ? ORDER BY id DESC""",
        (since,),
    ).fetchall()

    lines = [
        f"WEEKLY REPORT — {datetime.now(UTC).date().isoformat()}",
        f"Window: last {days} days",
        "",
        f"New claims discovered: {len(new_claims)}",
        f"Claims reviewed & approved: {len(reviewed_claims)}",
        f"Corrections recorded: {len(corrections)}",
        "",
    ]
    if reviewed_claims:
        lines.append("REVIEWED THIS WEEK")
        for c in reviewed_claims:
            lines.append(f"- {c['id']} [{c['status']}] {c['claim_text'][:100]}")
        lines.append("")
    by_status: dict[str, int] = {}
    for c in new_claims:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    if by_status:
        lines.append("NEW CLAIMS BY STATUS")
        for status, n in sorted(by_status.items()):
            lines.append(f"- {status}: {n}")
        lines.append("")
    if corrections:
        lines.append("CORRECTIONS")
        for c in corrections:
            lines.append(f"- {c['entity_id']}: {c['reason'] or 'no reason recorded'}")
        lines.append("")
    lines.append("Methodology: https://example.github.io/methodology.html")
    return "\n".join(lines)


def corporate_monthly_report(conn: sqlite3.Connection) -> str:
    """Monthly corporate digest: approved relationships + statements."""
    rels = conn.execute(
        """SELECT cr.*, o.name AS company_name
           FROM corporate_relationships cr
           JOIN organizations o ON o.id = cr.company_org_id
           WHERE cr.review_status = 'approved'
           ORDER BY o.name, cr.created_at"""
    ).fetchall()
    statements = conn.execute(
        """SELECT cs.*, o.name AS company_name FROM company_statements cs
           JOIN organizations o ON o.id = cs.organization_id
           ORDER BY cs.statement_date DESC LIMIT 50"""
    ).fetchall()

    lines = [
        f"CORPORATE ACCOUNTABILITY REPORT — {datetime.now(UTC).date().isoformat()}",
        "",
        f"Approved documented relationships: {len(rels)}",
        "",
    ]
    if rels:
        lines.append("RELATIONSHIPS")
        for r in rels:
            lines.append(
                f"- {r['company_name']}: {r['service']} for {r['customer']}"
                f" — {r['classification'].replace('_', ' ')}"
                f" ({r['id']})"
            )
        lines.append("")
    if statements:
        lines.append("COMPANY STATEMENTS")
        for s in statements:
            lines.append(
                f"- {s['company_name']} ({s['statement_date'] or 'undated'}):"
                f" {s['statement_text'][:120]}"
            )
        lines.append("")
    lines.append(
        "Note: documented commercial relationships are not automatically"
        " criminal conduct. Users decide what action to take."
    )
    return "\n".join(lines)


def fact_check_card_report(conn: sqlite3.Connection, *, limit: int = 20) -> str:
    """A batch of fact-check cards for approved claims, newest first."""
    claims = conn.execute(
        "SELECT * FROM claims WHERE review_status = 'approved' ORDER BY last_reviewed DESC LIMIT ?",
        (limit,),
    ).fetchall()
    lines = []
    for i, c in enumerate(claims, 1):
        if i > 1:
            lines.append("")
            lines.append("-" * 60)
            lines.append("")
        lines.append(short_post(conn, c["id"]))
    header = (
        f"FACT-CHECK CARD REPORT — {datetime.now(UTC).date().isoformat()}"
        f" ({len(claims)} approved claims)"
    )
    return header + "\n\n" + "\n".join(lines)


def evidence_counts_for_report(conn: sqlite3.Connection, claim_id: str) -> tuple[int, int]:
    ev = get_evidence_for_claim(conn, claim_id)
    sup = sum(1 for e in ev if e["relationship"] == "supports")
    con = sum(1 for e in ev if e["relationship"] == "contradicts")
    return sup, con


def claims_exported_for_reports(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM claims WHERE review_status = 'approved' ORDER BY id"
    ).fetchall()
    return [cast("sqlite3.Row", r) for r in rows]
