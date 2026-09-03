"""Claim lifecycle: creation, splitting, duplicate detection, status transitions."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from typing import cast

from app import audit
from app.constants import CLAIM_STATUSES, SPEAKER_TYPES, STATUS_EVIDENCE_REQUIREMENTS
from app.util import next_id, normalize_claim_text, utcnow_iso


class ClaimError(ValueError):
    pass


def create_claim(
    conn: sqlite3.Connection,
    *,
    claim_text: str,
    speaker: str,
    source_id: str,
    speaker_type: str = "other",
    organization_id: str | None = None,
    event_id: str | None = None,
    published_at: str | None = None,
    topic: str | None = None,
    importance: str | None = None,
    original_language: str = "en",
    translated_text: str | None = None,
    translation_method: str | None = None,
    actor: str = "system",
    claim_id: str | None = None,
) -> str:
    """Create a claim. Raises DuplicateClaimError on normalized-text duplicates."""
    text = claim_text.strip()
    if not text:
        msg = "claim_text must not be empty"
        raise ClaimError(msg)
    if speaker_type not in SPEAKER_TYPES:
        msg = f"unknown speaker_type {speaker_type!r}; known: {SPEAKER_TYPES}"
        raise ClaimError(msg)
    if not conn.execute("SELECT 1 FROM sources WHERE id = ?", (source_id,)).fetchone():
        msg = f"source {source_id} does not exist"
        raise ClaimError(msg)

    normalized = normalize_claim_text(text)
    dup = conn.execute(
        "SELECT id, speaker FROM claims WHERE normalized_claim = ?", (normalized,)
    ).fetchone()
    if dup:
        msg = f"duplicate claim: normalized text already recorded as {dup['id']}"
        raise DuplicateClaimError(msg, dup["id"])

    now = utcnow_iso()
    cid = claim_id or next_id(conn, "claims", "CLM")
    conn.execute(
        """INSERT INTO claims (id, claim_text, normalized_claim, speaker, speaker_type,
             organization_id, event_id, source_id, published_at, discovered_at,
             status, confidence, importance, topic, original_language, translated_text,
             translation_method, review_status, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', 0.0, ?, ?, ?, ?, ?,
                   'pending', 1, ?, ?)""",
        (
            cid,
            text,
            normalized,
            speaker,
            speaker_type,
            organization_id,
            event_id,
            source_id,
            published_at,
            now,
            importance,
            topic,
            original_language,
            translated_text,
            translation_method,
            now,
            now,
        ),
    )
    audit.log(conn, actor, "create", "claim", cid, {"speaker": speaker, "topic": topic})
    _sync_fts(conn, cid)
    return cid


class DuplicateClaimError(ClaimError):
    def __init__(self, message: str, existing_id: str) -> None:
        super().__init__(message)
        self.existing_id = existing_id


def _sync_fts(conn: sqlite3.Connection, claim_id: str) -> None:
    row = conn.execute(
        "SELECT id, claim_text, normalized_claim, translated_text FROM claims WHERE id = ?",
        (claim_id,),
    ).fetchone()
    conn.execute("DELETE FROM claims_fts WHERE claim_id = ?", (claim_id,))
    if row is None:
        return
    conn.execute(
        "INSERT INTO claims_fts (claim_id, claim_text, normalized_claim, translated_text)"
        " VALUES (?, ?, ?, ?)",
        (row["id"], row["claim_text"], row["normalized_claim"], row["translated_text"]),
    )


def set_status(
    conn: sqlite3.Connection,
    claim_id: str,
    status: str,
    *,
    actor: str = "system",
    reason: str | None = None,
    override: bool = False,
) -> None:
    """Transition claim status with invariant enforcement (agentodo §38).

    A claim cannot become supported/contradicted/etc. without linked evidence
    of the required relationship. `override` (human reviewer) may bypass only
    the review-status check, never the evidence invariants.
    """
    if status not in CLAIM_STATUSES:
        msg = f"unknown status {status!r}; known: {CLAIM_STATUSES}"
        raise ClaimError(msg)
    row = conn.execute(
        "SELECT status, review_status, revision FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        msg = f"claim {claim_id} does not exist"
        raise ClaimError(msg)
    if row["review_status"] != "approved" and not override and status != row["status"]:
        msg = (
            f"claim {claim_id} is not approved for publication; "
            f"review_status={row['review_status']} (human approval required)"
        )
        raise ClaimError(msg)

    required_rel, min_count = STATUS_EVIDENCE_REQUIREMENTS[status]
    if required_rel:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM claim_evidence ce JOIN evidence e ON e.id = ce.evidence_id"
            " WHERE ce.claim_id = ? AND ce.relationship = ? AND e.supports_claim IS NOT NULL",
            (claim_id, required_rel),
        ).fetchone()["n"]
        if n < min_count:
            msg = (
                f"invariant violation: status '{status}' requires at least "
                f"{min_count} linked evidence with relationship '{required_rel}'"
            )
            raise InvariantError(msg)

    old = row["status"]
    conn.execute(
        "UPDATE claims SET status = ?, updated_at = ?, revision = revision + 1 WHERE id = ?",
        (status, utcnow_iso(), claim_id),
    )
    audit.log(
        conn,
        actor,
        "status_change",
        "claim",
        claim_id,
        {"from": old, "to": status, "override": override},
        reason,
    )


class InvariantError(ClaimError):
    pass


def split_compound_claim(text: str) -> list[str]:
    """Split compound claims into atomic factual assertions (agentodo §8).

    Splits on causal and inferential connectives. 'X because Y, therefore Z'
    becomes ['X happened', 'Y caused X', 'Z follows from X and Y'] is the
    ideal; Phase 1 implements connective-based splitting which yields
    ['X happened', 'Y', 'Z'] segments. Returns [text] when not compound.
    """
    import re

    segments = re.split(
        r"(?:\s+because\s+|\s+therefore\s+|\s+thus\s+|\s+so\s+that\s+|\s*;\s+|\s*,\s+and\s+|\s+and\s+therefore\s+|\.\s+)",
        text.strip(),
        flags=re.IGNORECASE,
    )
    parts = [s.strip(" ,.;") for s in segments]
    parts = [p for p in parts if p and len(p) > 2]
    if len(parts) <= 1:
        return [text.strip()]
    # keep original capitalization sense: lowercase continuation fragments
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[0].lower() + p[1:] if p[:2].isupper() is False and p[0].isupper() else p)
    return out


def find_duplicates(conn: sqlite3.Connection, claim_text: str) -> list[sqlite3.Row]:
    """Find existing claims with identical normalized text."""
    return conn.execute(
        "SELECT id, claim_text, speaker, published_at FROM claims WHERE normalized_claim = ?",
        (normalize_claim_text(claim_text),),
    ).fetchall()


def get_claim(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    return cast("sqlite3.Row | None", row)


def claims_with_evidence_counts(
    conn: sqlite3.Connection, status: str | None = None
) -> list[sqlite3.Row]:
    """Claims joined with supporting/contradicting evidence counts."""
    q = """
        SELECT c.*, COUNT(CASE WHEN ce.relationship = 'supports' THEN 1 END) AS n_supporting,
               COUNT(CASE WHEN ce.relationship = 'contradicts' THEN 1 END) AS n_contradicting
        FROM claims c
        LEFT JOIN claim_evidence ce ON ce.claim_id = c.id
        WHERE (? IS NULL OR c.status = ?)
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """
    return conn.execute(q, (status, status)).fetchall()


def link_event(
    conn: sqlite3.Connection, claim_id: str, event_id: str, actor: str = "system"
) -> None:
    _require(conn, "events", event_id, "event")
    conn.execute(
        "UPDATE claims SET event_id = ?, updated_at = ? WHERE id = ?",
        (event_id, utcnow_iso(), claim_id),
    )
    audit.log(conn, actor, "update", "claim", claim_id, {"event_id": event_id})


def _require(conn: sqlite3.Connection, table: str, row_id: str, kind: str) -> None:
    if not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (row_id,)).fetchone():
        msg = f"{kind} {row_id} does not exist"
        raise ClaimError(msg)


def create_event(
    conn: sqlite3.Connection,
    *,
    title: str,
    description: str | None = None,
    location: str | None = None,
    occurred_on: str | None = None,
    event_type: str = "other",
    actor: str = "system",
    event_id: str | None = None,
) -> str:
    now = utcnow_iso()
    eid = event_id or next_id(conn, "events", "EVT")
    conn.execute(
        """INSERT INTO events (id, title, description, location, occurred_on, event_type,
             created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (eid, title, description, location, occurred_on, event_type, now, now),
    )
    audit.log(conn, actor, "create", "event", eid, {"title": title})
    return eid


def create_organization(
    conn: sqlite3.Connection,
    *,
    name: str,
    org_type: str = "other",
    country: str | None = None,
    website: str | None = None,
    notes: str | None = None,
    actor: str = "system",
    organization_id: str | None = None,
) -> str:
    now = utcnow_iso()
    oid = organization_id or next_id(conn, "organizations", "ORG")
    conn.execute(
        """INSERT INTO organizations (id, name, org_type, country, website, notes,
             created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (oid, name, org_type, country, website, notes, now, now),
    )
    audit.log(conn, actor, "create", "organization", oid, {"name": name})
    return oid


def create_person(
    conn: sqlite3.Connection,
    *,
    name: str,
    role: str | None = None,
    organization_id: str | None = None,
    notes: str | None = None,
    actor: str = "system",
    person_id: str | None = None,
) -> str:
    now = utcnow_iso()
    pid = person_id or next_id(conn, "people", "PER")
    conn.execute(
        """INSERT INTO people (id, name, role, organization_id, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (pid, name, role, organization_id, notes, now, now),
    )
    audit.log(conn, actor, "create", "person", pid, {"name": name})
    return pid


def search_claims(conn: sqlite3.Connection, query: str, *, limit: int = 50) -> list[sqlite3.Row]:
    """FTS5 keyword search over claim text. Falls back to LIKE on empty query."""
    if not query.strip():
        return conn.execute(
            "SELECT * FROM claims ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    # escape double quotes for FTS phrase queries
    q = '"' + query.strip().replace('"', '""') + '"'
    try:
        return conn.execute(
            "SELECT c.* FROM claims_fts f JOIN claims c ON c.id = f.claim_id"
            " WHERE claims_fts MATCH ? ORDER BY rank LIMIT ?",
            (q, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return conn.execute(
            "SELECT * FROM claims WHERE claim_text LIKE ? OR normalized_claim LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()


def pending_review_queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Review queue ordered by importance and evidence availability."""
    return conn.execute(
        """SELECT c.*,
                  COUNT(CASE WHEN ce.relationship = 'supports' THEN 1 END) AS n_supporting,
                  COUNT(CASE WHEN ce.relationship = 'contradicts' THEN 1 END) AS n_contradicting,
                  CASE c.importance WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                       WHEN 'medium' THEN 2 ELSE 3 END AS importance_rank
           FROM claims c
           LEFT JOIN claim_evidence ce ON ce.claim_id = c.id
           WHERE c.review_status IN ('pending', 'in_review')
           GROUP BY c.id
           ORDER BY importance_rank, c.discovered_at DESC"""
    ).fetchall()


def iter_all(conn: sqlite3.Connection) -> Iterable[sqlite3.Row]:
    return conn.execute("SELECT * FROM claims ORDER BY id").fetchall()
