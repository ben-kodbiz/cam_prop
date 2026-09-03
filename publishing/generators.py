"""Social content generation from structured, approved evidence (agentodo §28-30).

Flow: DATABASE -> CLAIM -> EVIDENCE -> ASSESSMENT -> HUMAN APPROVAL -> CONTENT.
Never generates harassment or targets individuals; only policies, claims,
institutions, documented actions and corporate decisions (§29).
"""

from __future__ import annotations

import sqlite3
from typing import cast

from app.evidence import get_evidence_for_claim


class PublishingError(ValueError):
    pass


def _claim_or_error(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        msg = f"claim {claim_id} does not exist"
        raise PublishingError(msg)
    if row["review_status"] != "approved":
        msg = f"claim {claim_id} is not approved; content generation requires human approval"
        raise PublishingError(msg)
    return cast("sqlite3.Row", row)


def _primary_citation(conn: sqlite3.Connection, claim_id: str) -> str:
    rows = get_evidence_for_claim(conn, claim_id)
    best = None
    for r in rows:
        if r["relationship"] != "supports":
            continue
        if best is None or (r["source_tier"] or 4) < (best["source_tier"] or 4):
            best = r
    if best is None:
        return "No primary evidence citation recorded."
    date = best["published_at"] or best["retrieved_at"] or "n.d."
    return f"{best['publisher'] or 'Primary source'}, {date}. {best['canonical_url']}"


def _base_block(conn: sqlite3.Connection, claim: sqlite3.Row) -> list[str]:
    return [
        "CLAIM CHECK",
        "",
        f"Claim: \u201c{claim['claim_text']}\u201d",
        f"Assessment: {claim['status'].replace('_', ' ').upper()}",
        f"Confidence: {claim['confidence']:.0%}",
    ]


def short_post(conn: sqlite3.Connection, claim_id: str) -> str:
    """Generate a short fact-check post (approved claims only)."""
    claim = _claim_or_error(conn, claim_id)
    lines = _base_block(conn, claim)
    lines += [
        "Why: assessment based on"
        f" {len(get_evidence_for_claim(conn, claim_id))} linked evidence records.",
        f"Primary evidence: {_primary_citation(conn, claim_id)}",
        f"Last reviewed: {claim['last_reviewed'] or 'not yet reviewed'}",
        f"Details: /claim/{claim_id}/",
    ]
    return "\n".join(lines)


def fact_check_card(conn: sqlite3.Connection, claim_id: str) -> str:
    """Generate a fact-check card block (approved claims only)."""
    claim = _claim_or_error(conn, claim_id)
    ev = get_evidence_for_claim(conn, claim_id)
    sup = [e for e in ev if e["relationship"] == "supports"]
    con = [e for e in ev if e["relationship"] == "contradicts"]
    lines = _base_block(conn, claim)
    lines += ["", "SUPPORTING EVIDENCE"]
    lines += [f"- {e['publisher'] or e['title']} [{e['source_tier']}]" for e in sup] or [
        "- none recorded"
    ]
    lines += ["", "CONTRADICTING EVIDENCE"]
    lines += [f"- {e['publisher'] or e['title']} [{e['source_tier']}]" for e in con] or [
        "- none recorded"
    ]
    lines += ["", "WHAT WE DON'T KNOW"]
    if claim["status"] in ("unknown", "insufficient_evidence", "disputed"):
        lines.append("- Evidence is incomplete or contested; see methodology page.")
    else:
        lines.append("- See claim page for open questions.")
    lines += ["", f"Primary evidence: {_primary_citation(conn, claim_id)}"]
    lines.append(f"Last reviewed: {claim['last_reviewed'] or 'not yet reviewed'}")
    return "\n".join(lines)


def carousel(conn: sqlite3.Connection, claim_id: str, *, slides: int = 5) -> list[str]:
    """Generate carousel slides (approved claims only)."""
    if not 3 <= slides <= 10:
        msg = "slides must be 3-10"
        raise PublishingError(msg)
    claim = _claim_or_error(conn, claim_id)
    ev = get_evidence_for_claim(conn, claim_id)
    cards: list[str] = []
    cards.append(f"CLAIM CHECK\n\n\u201c{claim['claim_text'][:180]}\u201d")
    cards.append(f"ASSESSMENT\n\n{claim['status'].replace('_', ' ').upper()}")
    sup = [e for e in ev if e["relationship"] == "supports"]
    if sup:
        e = sup[0]
        cards.append(
            "SUPPORTING EVIDENCE\n\n"
            f"{e['publisher'] or e['title']} — {e['published_at'] or e['retrieved_at']}"
        )
    else:
        cards.append("SUPPORTING EVIDENCE\n\nNo supporting evidence recorded.")
    con = [e for e in ev if e["relationship"] == "contradicts"]
    if con:
        e = con[0]
        cards.append(
            "CONTRADICTING EVIDENCE\n\n"
            f"{e['publisher'] or e['title']} — {e['published_at'] or e['retrieved_at']}"
        )
    elif slides > 4:
        cards.append("CONTRADICTING EVIDENCE\n\nNo contradicting evidence recorded.")
    cards.append(
        "SOURCES & METHOD\n\n"
        f"Primary evidence: {_primary_citation(conn, claim_id)}\n"
        f"Last reviewed: {claim['last_reviewed'] or 'not yet reviewed'}\n"
        f"Details: /claim/{claim_id}/"
    )
    while len(cards) < slides:
        cards.insert(len(cards) - 1, "WHAT WE DON'T KNOW\n\nSee claim page for open questions.")
    return cards[:slides]


def citation_line(conn: sqlite3.Connection, claim_id: str) -> str:
    """One-line citation for generated content (approved claims only)."""
    _claim_or_error(conn, claim_id)
    return f"Open Evidence {claim_id}: {_primary_citation(conn, claim_id)}"
