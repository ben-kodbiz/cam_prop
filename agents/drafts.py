"""LLM-assisted drafts (Phase 3): explanations and translations.

Drafts are stored in `claim_drafts` and touch nothing until a human calls
apply_draft(). Applying an explanation sets claims.explanation; applying a
translation sets claims.translated_text + translation_method='llm' (§42: an
AI translation is never the authoritative legal wording — the original text
always stays).
"""

from __future__ import annotations

import sqlite3
from typing import cast

from app import audit
from app.util import next_id, utcnow_iso

from agents.llm import LLMClient


class DraftError(ValueError):
    pass


EXPLANATION_PROMPT = """You write short, neutral explanations for an
evidence project. Rules:
- Calm, precise, evidence-based; no inflammatory language.
- State what the linked evidence supports or contradicts.
- Explicitly say what remains unknown when evidence is missing.
- Never assert anything not present in the provided evidence.
- Maximum 3 short sentences."""

TRANSLATION_PROMPT = """You are a careful translator. Translate the text
to the target language faithfully and neutrally. Preserve meaning; do not
add, interpret, or omit. Legal terminology must stay close to the source."""


def draft_explanation(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    client: LLMClient,
    model: str = "",
) -> str:
    """Draft a short 'why' explanation from the claim's linked evidence."""
    draft_text = _draft(conn, claim_id, client, EXPLANATION_PROMPT, kind="explanation")
    _store(conn, claim_id=claim_id, kind="explanation", draft_text=draft_text, model=model)
    return draft_text


def draft_translation(
    conn: sqlite3.Connection,
    *,
    claim_id: str,
    target_language: str,
    client: LLMClient,
    model: str = "",
) -> str:
    """Draft a translation of the claim text (original text is never replaced)."""
    row = conn.execute("SELECT claim_text FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        msg = f"claim {claim_id} does not exist"
        raise DraftError(msg)
    user = f"Target language: {target_language}\n\nText:\n{row['claim_text']}"
    draft_text = client.complete(TRANSLATION_PROMPT, user).strip()
    if not draft_text:
        msg = "LLM returned an empty translation"
        raise DraftError(msg)
    _store(conn, claim_id=claim_id, kind="translation", draft_text=draft_text, model=model)
    return draft_text


def _draft(
    conn: sqlite3.Connection, claim_id: str, client: LLMClient, system: str, *, kind: str
) -> str:
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        msg = f"claim {claim_id} does not exist"
        raise DraftError(msg)
    from app.evidence import get_evidence_for_claim

    ev = get_evidence_for_claim(conn, claim_id)
    parts = [f"Claim: {claim['claim_text']}", f"Current assessment: {claim['status']}"]
    sup = [e for e in ev if e["relationship"] == "supports"]
    con = [e for e in ev if e["relationship"] == "contradicts"]
    parts.append(f"Supporting evidence: {len(sup)}")
    for e in sup[:5]:
        excerpt = (e["excerpt"] or e["context"] or "")[:200]
        parts.append(f"  - {e['title']}: {excerpt}")
    parts.append(f"Contradicting evidence: {len(con)}")
    for e in con[:5]:
        excerpt = (e["excerpt"] or e["context"] or "")[:200]
        parts.append(f"  - {e['title']}: {excerpt}")
    if not ev:
        parts.append("No linked evidence yet.")
    draft = client.complete(system, "\n".join(parts)).strip()
    if not draft:
        msg = f"LLM returned an empty {kind} draft"
        raise DraftError(msg)
    return draft


def _store(
    conn: sqlite3.Connection, *, claim_id: str, kind: str, draft_text: str, model: str
) -> str:
    now = utcnow_iso()
    did = next_id(conn, "claim_drafts", "DFT")
    conn.execute(
        """INSERT INTO claim_drafts (id, claim_id, kind, draft_text, model,
             status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (did, claim_id, kind, draft_text, model, now, now),
    )
    audit.log(conn, "llm", "create", "draft", did, {"claim_id": claim_id, "kind": kind})
    return did


def pending_drafts(conn: sqlite3.Connection, *, claim_id: str | None = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM claim_drafts WHERE status = 'pending'"
    params: list[object] = []
    if claim_id:
        q += " AND claim_id = ?"
        params.append(claim_id)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    return [cast("sqlite3.Row", r) for r in rows]


def apply_draft(
    conn: sqlite3.Connection,
    draft_id: str,
    *,
    reviewer: str,
) -> str:
    """Human applies a pending draft to the claim. Returns the new value."""
    row = conn.execute("SELECT * FROM claim_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        msg = f"draft {draft_id} does not exist"
        raise DraftError(msg)
    if row["status"] != "pending":
        msg = f"draft {draft_id} is already {row['status']}"
        raise DraftError(msg)
    now = utcnow_iso()
    if row["kind"] == "explanation":
        conn.execute(
            "UPDATE claims SET explanation = ?, updated_at = ? WHERE id = ?",
            (row["draft_text"], now, row["claim_id"]),
        )
        new_value: str = str(row["draft_text"])
    elif row["kind"] == "translation":
        conn.execute(
            "UPDATE claims SET translated_text = ?, translation_method = 'llm',"
            " updated_at = ? WHERE id = ?",
            (row["draft_text"], now, row["claim_id"]),
        )
        new_value = str(row["draft_text"])
    else:
        msg = f"unknown draft kind {row['kind']!r}"
        raise DraftError(msg)
    conn.execute(
        "UPDATE claim_drafts SET status = 'applied', reviewed_at = ?, reviewer = ?,"
        " updated_at = ? WHERE id = ?",
        (now, reviewer, now, draft_id),
    )
    audit.log(
        conn,
        reviewer,
        "apply",
        "draft",
        draft_id,
        {"claim_id": row["claim_id"], "kind": row["kind"]},
    )
    return new_value


def reject_draft(
    conn: sqlite3.Connection,
    draft_id: str,
    *,
    reviewer: str,
    reason: str | None = None,
) -> None:
    row = conn.execute("SELECT * FROM claim_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        msg = f"draft {draft_id} does not exist"
        raise DraftError(msg)
    if row["status"] != "pending":
        msg = f"draft {draft_id} is already {row['status']}"
        raise DraftError(msg)
    now = utcnow_iso()
    conn.execute(
        "UPDATE claim_drafts SET status = 'rejected', reviewed_at = ?, reviewer = ?,"
        " updated_at = ? WHERE id = ?",
        (now, reviewer, now, draft_id),
    )
    audit.log(
        conn,
        reviewer,
        "reject",
        "draft",
        draft_id,
        {"claim_id": row["claim_id"], "kind": row["kind"]},
        reason,
    )
