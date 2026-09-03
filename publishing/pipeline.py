"""Publication pipeline (Phase 7): from approved DB content to artifacts.

The pipeline writes generated artifacts (fact-check cards, reports) into
publishing/output/, marks subjects as published (audit-logged), and never
publishes anything whose review_status != 'approved'. High-impact subjects
additionally require a named reviewer (checked by the review gate).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.review import record_publication


class PublishError(ValueError):
    pass


def publish_claim(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    output_dir: Path,
    actor: str = "system",
    with_card: bool = True,
) -> dict[str, object]:
    """Publish one approved claim: web_page publication + card artifact."""
    from publishing.generators import fact_check_card

    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if row is None:
        msg = f"claim {claim_id} does not exist"
        raise PublishError(msg)
    if row["review_status"] != "approved":
        msg = (
            f"claim {claim_id} has review_status {row['review_status']!r};"
            " human approval is required before publishing"
        )
        raise PublishError(msg)

    record_publication(
        conn, subject_type="claim", subject_id=claim_id, format="web_page", actor=actor
    )
    artifacts: list[str] = []
    if with_card:
        card = fact_check_card(conn, claim_id)
        artifacts.append(_write_artifact(output_dir, f"card-{claim_id}.txt", card))
    return {"claim_id": claim_id, "publication": "web_page", "artifacts": artifacts}


def publish_report(
    conn: sqlite3.Connection,
    report_text: str,
    *,
    name: str,
    output_dir: Path,
    actor: str = "system",
) -> str:
    """Persist a generated report artifact (reports are not auto-published)."""
    return _write_artifact(output_dir, f"report-{name}.txt", report_text)


def _write_artifact(output_dir: Path, filename: str, text: str) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    path.write_text(text + "\n", encoding="utf-8")
    return str(path)
