"""Deterministic evidence agent (agentodo §9).

Phase 1 is fully deterministic: no LLM. It compares linked evidence,
identifies contradictions and gaps, and produces a *provisional*
assessment. It never changes the database status of high-impact claims.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from app.evidence import get_evidence_for_claim, missing_evidence
from app.util import utcnow_iso


@dataclass
class EvidenceAssessment:
    claim_id: str
    assessment: str
    confidence: float
    supporting_evidence: list[dict[str, object]] = field(default_factory=list)
    contradicting_evidence: list[dict[str, object]] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    reasoning_summary: str = ""
    high_impact: bool = False
    generated_at: str = ""

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, sort_keys=True, indent=2)


def assess_claim(conn: sqlite3.Connection, claim_id: str) -> EvidenceAssessment:
    """Provisional assessment from linked evidence only. No invention."""
    claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if claim is None:
        msg = f"claim {claim_id} does not exist"
        raise ValueError(msg)
    rows = get_evidence_for_claim(conn, claim_id)
    gaps = missing_evidence(conn, claim_id)

    supporting = [r for r in rows if r["relationship"] == "supports"]
    contradicting = [r for r in rows if r["relationship"] == "contradicts"]

    def evdict(r: sqlite3.Row) -> dict[str, object]:
        return {
            "evidence_id": r["id"],
            "source_id": r["source_id"],
            "publisher": r["publisher"],
            "source_tier": r["source_tier"],
            "strength": r["strength"],
            "excerpt": r["excerpt"],
            "url": r["canonical_url"],
        }

    n_sup = len(supporting)
    n_con = len(contradicting)
    sup_strength = max((r["strength"] or 0.0 for r in supporting), default=0.0)
    con_strength = max((r["strength"] or 0.0 for r in contradicting), default=0.0)

    # Deterministic decision rules. These are provisional statuses only;
    # the human reviewer makes the final classification (agentodo §6).
    if n_sup == 0 and n_con == 0:
        assessment = "insufficient_evidence" if not gaps["missing"] else "unknown"
        confidence = 0.1
        reasoning = "No linked evidence for or against the claim."
    elif n_con == 0 and n_sup > 0:
        assessment = "mostly_supported" if sup_strength < 0.6 else "supported"
        confidence = round(0.4 + 0.5 * min(1.0, sup_strength) * min(1.0, n_sup / 3), 2)
        reasoning = (
            f"{n_sup} supporting evidence records, strongest {sup_strength:.2f};"
            " no contradicting evidence found yet."
        )
    elif n_sup == 0 and n_con > 0:
        assessment = "unsupported"
        confidence = round(0.4 + 0.5 * min(1.0, con_strength) * min(1.0, n_con / 3), 2)
        reasoning = (
            f"{n_con} contradicting evidence records, strongest {con_strength:.2f};"
            " no supporting evidence found."
        )
    else:
        # both sides present
        total = n_sup + n_con
        ratio = n_sup / total
        if 0.35 <= ratio <= 0.65 or abs(sup_strength - con_strength) < 0.15:
            assessment = "disputed"
            confidence = 0.5
            reasoning = (
                f"Evidence is split: {n_sup} supporting vs {n_con} contradicting"
                " with comparable strength."
            )
        elif ratio > 0.65:
            assessment = "mostly_supported" if sup_strength >= 0.5 else "insufficient_evidence"
            confidence = round(0.4 + 0.3 * sup_strength, 2)
            reasoning = (
                f"More supporting than contradicting evidence, but contradictions exist ({n_con})."
            )
        else:
            assessment = "misleading" if con_strength >= 0.6 else "disputed"
            confidence = round(0.4 + 0.3 * con_strength, 2)
            reasoning = (
                f"Contradicting evidence outweighs supporting evidence ({n_con} vs {n_sup})."
            )

    confidence = round(min(0.9, max(0.0, confidence)), 2)
    high_impact = (claim["topic"] or "") in (
        "deaths",
        "war_crimes",
        "genocide",
        "terrorism",
        "individual_accusations",
        "corporate_allegations",
        "illegal_conduct",
        "financial_relationships",
        "military_activity",
        "international_law",
    )
    if high_impact:
        reasoning += (
            " High-impact topic: provisional only; human review is mandatory"
            " before any publication."
        )
    if not gaps["has_primary_support"] and supporting:
        reasoning += " Note: no tier-1 primary support among supporting evidence."
        confidence = round(confidence * 0.8, 2)

    return EvidenceAssessment(
        claim_id=claim_id,
        assessment=assessment,
        confidence=confidence,
        supporting_evidence=[evdict(r) for r in supporting],
        contradicting_evidence=[evdict(r) for r in contradicting],
        missing_evidence=(gaps["missing"] or (["primary_source"] if supporting else [])),
        reasoning_summary=reasoning,
        high_impact=high_impact,
        generated_at=utcnow_iso(),
    )


def assess_pending(conn: sqlite3.Connection) -> list[dict[str, object]]:
    """Assess all pending claims into review-queue entries."""
    out = []
    for row in conn.execute(
        "SELECT id FROM claims WHERE review_status IN ('pending', 'in_review')"
    ).fetchall():
        a = assess_claim(conn, row["id"])
        out.append(json.loads(a.to_json()))
    return out
