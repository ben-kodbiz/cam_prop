"""Evidence agent tests: deterministic provisional assessment."""

from __future__ import annotations

import json

import pytest
from agents.evidence_agent import EvidenceAssessment, assess_claim, assess_pending
from app.claims import create_claim
from app.evidence import create_evidence, link_evidence
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


def test_no_evidence_yields_unknown(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Unevidenced.", speaker="X", source_id=src)
    a = assess_claim(tmp_db, cid)
    assert a.assessment in ("unknown", "insufficient_evidence")
    assert a.confidence <= 0.2
    assert a.supporting_evidence == []
    assert a.contradicting_evidence == []


def test_supported_by_strong_evidence(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Strong.", speaker="X", source_id=src)
    icj_src = create_source(
        tmp_db,
        url="https://icj.example/order",
        title="ICJ order",
        source_type="icj",
        content_text="order",
    )
    for _ in range(3):
        ev = create_evidence(
            tmp_db,
            source_id=icj_src,
            dimensions={
                "source_quality": 5,
                "primary_source": True,
                "independence": 5,
                "directness": 5,
                "corroboration": 4,
                "contradiction": 0,
                "recency": 5,
            },
        )
        link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship="supports")
    a = assess_claim(tmp_db, cid)
    assert a.assessment == "supported"
    assert a.confidence > 0.6


def test_contradicted_assessment(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Weak.", speaker="X", source_id=src)
    ev = create_evidence(
        tmp_db,
        source_id=src,
        dimensions={
            "source_quality": 4,
            "primary_source": True,
            "independence": 4,
            "directness": 5,
            "corroboration": 3,
            "contradiction": 0,
            "recency": 4,
        },
    )
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship="contradicts")
    a = assess_claim(tmp_db, cid)
    assert a.assessment == "unsupported"
    assert len(a.contradicting_evidence) == 1


def test_disputed_when_evidence_splits(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Split.", speaker="X", source_id=src)
    for rel in ("supports", "supports", "contradicts"):
        ev = create_evidence(
            tmp_db,
            source_id=src,
            dimensions={
                "source_quality": 4,
                "primary_source": True,
                "independence": 3,
                "directness": 4,
                "corroboration": 2,
                "contradiction": 0,
                "recency": 4,
            },
        )
        link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship=rel)
    a = assess_claim(tmp_db, cid)
    assert a.assessment == "disputed"


def test_high_impact_flag(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="High.", speaker="X", source_id=src, topic="war_crimes")
    a = assess_claim(tmp_db, cid)
    assert a.high_impact is True
    assert "human review" in a.reasoning_summary.lower()


def test_json_roundtrip(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="JSON.", speaker="X", source_id=src)
    a = assess_claim(tmp_db, cid)
    data = json.loads(a.to_json())
    assert data["claim_id"] == cid
    assert EvidenceAssessment(**data).assessment == a.assessment


def test_assess_pending_only_pending(tmp_db, src):
    create_claim(tmp_db, claim_text="Pending one.", speaker="X", source_id=src)
    approved = create_claim(tmp_db, claim_text="Approved one.", speaker="X", source_id=src)
    from app.review import submit_review

    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=approved,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    results = assess_pending(tmp_db)
    ids = [r["claim_id"] for r in results]
    assert approved not in ids
    assert len(ids) == 1
