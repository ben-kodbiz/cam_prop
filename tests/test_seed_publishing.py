"""Seed and publishing tests."""

from __future__ import annotations

from app.seed import seed
from publishing.generators import (
    carousel,
    citation_line,
    fact_check_card,
    short_post,
)


def test_seed_creates_fixture_world(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    assert ids["claim_reviewed"].startswith("CLM-")
    assert ids["legal_document"].startswith("LGL-")
    assert ids["corporate_relationship"].startswith("CORP-")
    assert ids["alternative"].startswith("ALT-")
    counts = {
        t: tmp_db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in (
            "sources",
            "claims",
            "evidence",
            "reviews",
            "audit_log",
            "legal_documents",
            "corporate_relationships",
            "company_statements",
            "alternatives",
        )
    }
    assert counts["sources"] == 3
    assert counts["claims"] == 3
    assert counts["evidence"] == 2
    assert counts["reviews"] == 4  # claim, legal, relationship, alternative
    assert counts["legal_documents"] == 1
    assert counts["corporate_relationships"] == 1
    assert counts["company_statements"] == 1
    assert counts["alternatives"] == 1
    assert counts["audit_log"] > 0


def test_seed_claim_approved_and_supported(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    row = tmp_db.execute(
        "SELECT status, review_status, last_reviewed FROM claims WHERE id = ?",
        (ids["claim_reviewed"],),
    ).fetchone()
    assert row["status"] == "supported"
    assert row["review_status"] == "approved"
    assert row["last_reviewed"]


def test_generators_require_approval(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    for fn in (short_post, fact_check_card, citation_line):
        try:
            fn(tmp_db, ids["claim_pending"])
            raise AssertionError("expected PublishingError")
        except Exception as e:
            assert "approved" in str(e)


def test_short_post_contains_required_blocks(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    post = short_post(tmp_db, ids["claim_reviewed"])
    assert "CLAIM CHECK" in post
    assert "Assessment:" in post
    assert ids["claim_reviewed"] in post
    assert "Primary evidence:" in post
    assert "Last reviewed:" in post


def test_fact_check_card_evidence_lists(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    card = fact_check_card(tmp_db, ids["claim_reviewed"])
    assert "SUPPORTING EVIDENCE" in card
    assert "CONTRADICTING EVIDENCE" in card
    assert "WHAT WE DON'T KNOW" in card


def test_carousel_slides(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    slides = carousel(tmp_db, ids["claim_reviewed"], slides=5)
    assert 3 <= len(slides) <= 10
    assert slides[0].startswith("CLAIM CHECK")


def test_carousel_slide_count_validated(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    try:
        carousel(tmp_db, ids["claim_reviewed"], slides=2)
        raise AssertionError("expected PublishingError")
    except Exception as e:
        assert "slides" in str(e)
