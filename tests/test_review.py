"""Review gate tests: checklist enforcement, publication guard, audit trail."""

from __future__ import annotations

import pytest
from app.claims import create_claim, set_status
from app.evidence import create_evidence, link_evidence
from app.review import (
    ReviewError,
    record_publication,
    review_history,
    submit_review,
)
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


def _claim(tmp_db, src, topic=None):
    return create_claim(
        tmp_db, claim_text=f"Claim {topic}.", speaker="X", source_id=src, topic=topic
    )


def test_review_flow_approve(tmp_db, src):
    cid = _claim(tmp_db, src)
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=cid,
        reviewer="alice",
        decision="approve",
        checklist={},
    )
    hist = review_history(tmp_db, "claim", cid)
    assert hist[0]["decision"] == "approve"
    row = tmp_db.execute(
        "SELECT review_status, reviewer FROM claims WHERE id = ?", (cid,)
    ).fetchone()
    assert row["review_status"] == "approved"


def test_high_impact_requires_full_checklist(tmp_db, src):
    cid = _claim(tmp_db, src, topic="war_crimes")
    with pytest.raises(ReviewError, match="checklist"):
        submit_review(
            tmp_db,
            subject_type="claim",
            subject_id=cid,
            reviewer="alice",
            decision="approve",
            checklist={},
        )
    full = {
        k: True
        for k in (
            "original_claim_represented",
            "speaker_identified",
            "date_correct",
            "primary_source",
            "contradictory_evidence_searched",
            "fact_separated_from_interpretation",
            "allegation_distinguished_from_finding",
            "legal_terminology_accurate",
            "other_party_response_included",
            "citations_correct",
            "uncertainty_stated",
            "no_false_certainty",
        )
    }
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=cid,
        reviewer="alice",
        decision="approve",
        checklist=full,
    )
    assert review_history(tmp_db, "claim", cid)[0]["decision"] == "approve"


def test_reject_and_request_evidence(tmp_db, src):
    cid = _claim(tmp_db, src)
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=cid,
        reviewer="bob",
        decision="reject",
        checklist={},
        notes="misrepresented",
    )
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=cid,
        reviewer="bob",
        decision="request_evidence",
        checklist={},
    )
    row = tmp_db.execute("SELECT review_status FROM claims WHERE id = ?", (cid,)).fetchone()
    assert row["review_status"] == "pending"  # request_evidence resets to pending


def test_publish_requires_approval(tmp_db, src):
    cid = _claim(tmp_db, src)
    with pytest.raises(ReviewError, match="approved"):
        record_publication(tmp_db, subject_type="claim", subject_id=cid, format="web_page")
    submit_review(
        tmp_db, subject_type="claim", subject_id=cid, reviewer="r", decision="approve", checklist={}
    )
    pid = record_publication(tmp_db, subject_type="claim", subject_id=cid, format="web_page")
    assert pid.startswith("PUB-")


def test_reviewer_required(tmp_db, src):
    cid = _claim(tmp_db, src)
    with pytest.raises(ReviewError, match="reviewer"):
        submit_review(
            tmp_db, subject_type="claim", subject_id=cid, reviewer=" ", decision="approve"
        )


def test_audit_trail_records_everything(tmp_db, src):
    cid = _claim(tmp_db, src, topic="deaths")
    full = {
        k: True
        for k in (
            "original_claim_represented",
            "speaker_identified",
            "date_correct",
            "primary_source",
            "contradictory_evidence_searched",
            "fact_separated_from_interpretation",
            "allegation_distinguished_from_finding",
            "legal_terminology_accurate",
            "other_party_response_included",
            "citations_correct",
            "uncertainty_stated",
            "no_false_certainty",
        )
    }
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=cid,
        reviewer="alice",
        decision="approve",
        checklist=full,
    )
    ev = create_evidence(
        tmp_db, source_id=src, dimensions={"source_quality": 5, "primary_source": True}
    )
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship="supports")
    set_status(tmp_db, cid, "supported", actor="alice", override=True)
    actions = [
        r["action"]
        for r in tmp_db.execute(
            "SELECT action FROM audit_log WHERE entity_type = 'claim' AND entity_id = ?"
            " ORDER BY id",
            (cid,),
        ).fetchall()
    ]
    assert "create" in actions
    assert "approve" in actions
    assert "status_change" in actions


def test_unknown_subject_rejected(tmp_db, src):
    with pytest.raises(ReviewError, match="unknown subject_type"):
        submit_review(
            tmp_db, subject_type="planet", subject_id="X", reviewer="r", decision="approve"
        )
    with pytest.raises(ReviewError, match="does not exist"):
        submit_review(
            tmp_db,
            subject_type="claim",
            subject_id="CLM-2026-9999",
            reviewer="r",
            decision="approve",
        )
