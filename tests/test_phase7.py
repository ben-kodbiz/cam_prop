"""Phase 7 tests: analytics, corrections, retraction, reports, pipeline."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.analytics import compute_stats
from app.corrections import (
    CORRECTION_KINDS,
    CorrectionError,
    correct_claim,
    correction_history,
    retract_publication,
)
from app.review import record_publication
from app.seed import seed
from publishing.pipeline import PublishError, publish_claim
from publishing.reports import (
    corporate_monthly_report,
    fact_check_card_report,
    weekly_report,
)


@dataclass
class Seeded:
    conn: sqlite3.Connection
    ids: dict


@pytest.fixture()
def seeded(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    tmp_db.commit()
    return Seeded(conn=tmp_db, ids=ids)


def _publish_seeded(seeded):
    record_publication(
        seeded.conn,
        subject_type="claim",
        subject_id=seeded.ids["claim_reviewed"],
        format="web_page",
    )


# ---------------------------------------------------------------------------
# Analytics (§43)
# ---------------------------------------------------------------------------


def test_compute_stats_shape(seeded):
    stats = compute_stats(seeded.conn, days=30)
    assert stats["claims"]["total"] == 3
    assert stats["claims"]["by_status"]["supported"] == 1
    assert stats["claims"]["by_review"]["approved"] == 1
    assert stats["quality"]["review_coverage"] > 0
    assert stats["other"]["legal_documents"] == 1
    assert stats["other"]["publications"] == 0
    assert stats["sources"]["books"] == 0


def test_analytics_evidence_depth(seeded):
    stats = compute_stats(seeded.conn)
    assert stats["evidence"]["avg_per_approved_claim"] >= 1.0


def test_analytics_citation_completeness(seeded):
    stats = compute_stats(seeded.conn)
    assert stats["quality"]["citation_completeness"] == 1.0


def test_analytics_empty_db(tmp_db):
    stats = compute_stats(tmp_db)
    assert stats["claims"]["total"] == 0
    assert stats["quality"]["correction_rate"] == 0.0


# ---------------------------------------------------------------------------
# Corrections & retraction (§21)
# ---------------------------------------------------------------------------


def test_correction_requires_reason(seeded):
    with pytest.raises(CorrectionError, match="reason is mandatory"):
        correct_claim(
            seeded.conn, seeded.ids["claim_reviewed"], kind="correction", reason="  ", reviewer="r"
        )


def test_correction_unknown_kind(seeded):
    with pytest.raises(CorrectionError, match="kind"):
        correct_claim(
            seeded.conn,
            seeded.ids["claim_reviewed"],
            kind="rewrite_history",
            reason="x",
            reviewer="r",
        )
    assert "rewrite_history" not in CORRECTION_KINDS


def test_correction_updates_revision_and_audits(seeded):
    claim_id = seeded.ids["claim_reviewed"]
    before = seeded.conn.execute(
        "SELECT revision FROM claims WHERE id = ?", (claim_id,)
    ).fetchone()["revision"]
    after = correct_claim(
        seeded.conn,
        claim_id,
        kind="clarification",
        reason="Wording tightened after re-check",
        reviewer="alice",
        new_explanation="Updated short explanation.",
    )
    assert after == before + 1
    history = correction_history(seeded.conn, "claim", claim_id)
    kinds = [h["action"] for h in history]
    assert "correction" in kinds
    row = seeded.conn.execute("SELECT explanation FROM claims WHERE id = ?", (claim_id,)).fetchone()
    assert row["explanation"] == "Updated short explanation."


def test_correction_requires_approved_claim(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")  # claim_pending not approved
    with pytest.raises(CorrectionError, match="not approved"):
        correct_claim(tmp_db, ids["claim_pending"], kind="correction", reason="x", reviewer="r")


def test_retract_and_republish_cycle(seeded):
    claim_id = seeded.ids["claim_reviewed"]
    _publish_seeded(seeded)
    n = retract_publication(
        seeded.conn,
        subject_type="claim",
        subject_id=claim_id,
        actor="alice",
        reason="cited source removed",
    )
    assert n == 1
    live = seeded.conn.execute(
        "SELECT COUNT(*) FROM publications WHERE retracted_at IS NULL"
    ).fetchone()[0]
    assert live == 0
    # republishing clears retracted_at (audit-trailed, never silent)
    record_publication(seeded.conn, subject_type="claim", subject_id=claim_id, format="web_page")
    live = seeded.conn.execute(
        "SELECT COUNT(*) FROM publications WHERE retracted_at IS NULL"
    ).fetchone()[0]
    assert live == 1


def test_retract_requires_reason(seeded):
    _publish_seeded(seeded)
    with pytest.raises(CorrectionError, match="reason is mandatory"):
        retract_publication(
            seeded.conn,
            subject_type="claim",
            subject_id=seeded.ids["claim_reviewed"],
            actor="a",
            reason=" ",
        )


def test_retract_without_publication_fails(seeded):
    with pytest.raises(CorrectionError, match="no live publication"):
        retract_publication(
            seeded.conn,
            subject_type="claim",
            subject_id=seeded.ids["claim_reviewed"],
            actor="a",
            reason="x",
        )


# ---------------------------------------------------------------------------
# Reports & publishing pipeline
# ---------------------------------------------------------------------------


def test_weekly_report_contents(seeded):
    text = weekly_report(seeded.conn)
    assert "WEEKLY REPORT" in text
    assert "Claims reviewed & approved: 1" in text
    assert seeded.ids["claim_reviewed"] in text


def test_corporate_report_contents(seeded):
    text = corporate_monthly_report(seeded.conn)
    assert "CORPORATE ACCOUNTABILITY REPORT" in text
    assert "ExampleCorp" in text
    assert "not automatically" in text  # §12 disclaimer


def test_cards_report_uses_approved_claims(seeded):
    text = fact_check_card_report(seeded.conn, limit=10)
    assert "FACT-CHECK CARD REPORT" in text
    assert "CLAIM CHECK" in text


def test_publish_claim_writes_artifact(seeded, tmp_path):
    out = tmp_path / "out"
    result = publish_claim(seeded.conn, seeded.ids["claim_reviewed"], output_dir=out)
    assert result["publication"] == "web_page"
    artifacts = result["artifacts"]
    assert isinstance(artifacts, list) and artifacts
    card = Path(str(artifacts[0]))
    assert card.is_file()
    assert "CLAIM CHECK" in card.read_text()
    pub = seeded.conn.execute(
        "SELECT COUNT(*) FROM publications WHERE subject_type = 'claim' AND retracted_at IS NULL"
    ).fetchone()[0]
    assert pub == 1


def test_publish_rejects_unapproved(seeded, tmp_path):
    with pytest.raises(PublishError, match="approval"):
        publish_claim(seeded.conn, seeded.ids["claim_pending"], output_dir=tmp_path / "out")


def test_stats_json_exported(tmp_db, tmp_path):
    from app.export import export_site_data

    seed(tmp_db, archive_dir=tmp_path / "archive")
    tmp_db.commit()
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    counts = export_site_data(db_path, tmp_path / "web")
    assert counts["stats.json"] == 1
    stats = json.loads((tmp_path / "web" / "data" / "stats.json").read_text())
    assert stats["claims"]["total"] == 3
    assert "correction_rate" in stats["quality"]
