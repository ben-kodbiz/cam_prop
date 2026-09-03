"""LLM-assisted claim extraction (Phase 3, agentodo §7-8).

The LLM proposes claims from source text; the pipeline enforces the rules
afterwards: compound splitting, duplicate detection, mandatory source
linkage. Every accepted proposal is stored as a *pending* claim — a human
still reviews before anything publishes. The LLM never sets a status.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.claims import DuplicateClaimError, create_claim, split_compound_claim

from agents.llm import LLMClient, parse_json_block

SYSTEM_PROMPT = """You are a claim extraction assistant for an evidence
documentation project. You extract factual claims made by speakers in the
given text. Rules:
- Extract only claims actually stated in the text; never invent.
- Each claim must be a single atomic factual assertion.
- Identify the speaker (person or organization) as stated in the text.
- Do not assess truth. Do not add opinions or context.
Return JSON: {"claims": [{"text": "...", "speaker": "...", "speaker_type":
"government|military|company|media|activist|individual|un_body|other",
"date": "YYYY-MM-DD or null"}]}"""


class ExtractionError(RuntimeError):
    pass


def extract_claims(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    text: str,
    client: LLMClient,
    published_at: str | None = None,
    topic: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Propose claims from `text`, create pending claims for new ones.

    Returns counts. Duplicates are skipped and reported; nothing is
    published and no status is ever set by this function.
    """
    row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if row is None:
        msg = f"source {source_id} does not exist"
        raise ExtractionError(msg)
    if not text.strip():
        msg = "no text to extract from"
        raise ExtractionError(msg)

    raw = client.complete(SYSTEM_PROMPT, text[:12000], json_mode=True)
    data = parse_json_block(raw)
    proposals = data.get("claims") if isinstance(data, dict) else None
    if not isinstance(proposals, list):
        msg = "LLM reply missing 'claims' list"
        raise ExtractionError(msg)

    created: list[str] = []
    duplicates: list[str] = []
    split_total = 0
    for item in proposals[:limit]:
        if not isinstance(item, dict):
            continue
        claim_text = str(item.get("text") or "").strip()
        speaker = str(item.get("speaker") or "").strip() or "Unknown speaker"
        speaker_type = item.get("speaker_type") or "other"
        date = item.get("date") or published_at
        if not claim_text:
            continue
        parts = split_compound_claim(claim_text)
        split_total += max(0, len(parts) - 1)
        for part in parts:
            try:
                cid = create_claim(
                    conn,
                    claim_text=part,
                    speaker=speaker,
                    speaker_type=str(speaker_type),
                    source_id=source_id,
                    published_at=str(date) if date else None,
                    topic=topic,
                    actor="llm-extraction",
                )
                created.append(cid)
            except DuplicateClaimError:
                duplicates.append(part)
    return {
        "source_id": source_id,
        "proposed": len(proposals),
        "created": len(created),
        "claim_ids": created,
        "duplicates": len(duplicates),
        "compound_splits": split_total,
    }
