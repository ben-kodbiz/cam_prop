"""Evidence tests: dimensions, linking, strength scoring, gaps."""

from __future__ import annotations

import json

import pytest
from app.claims import create_claim
from app.evidence import (
    EvidenceError,
    create_evidence,
    evidence_strength,
    get_evidence_for_claim,
    link_evidence,
    missing_evidence,
    update_strengths,
)
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


@pytest.fixture()
def claim(tmp_db, src):
    return create_claim(tmp_db, claim_text="C.", speaker="X", source_id=src)


def test_dimensions_validated(tmp_db, src):
    with pytest.raises(EvidenceError, match="0-5"):
        create_evidence(tmp_db, source_id=src, dimensions={"source_quality": 9})
    with pytest.raises(EvidenceError, match="bool"):
        create_evidence(tmp_db, source_id=src, dimensions={"primary_source": "yes"})


def test_excerpt_length_capped(tmp_db, src):
    with pytest.raises(EvidenceError, match="500"):
        create_evidence(tmp_db, source_id=src, excerpt="x" * 501)


def test_link_relationship_sets_supports_flag(tmp_db, src, claim):
    sup = create_evidence(tmp_db, source_id=src)
    con = create_evidence(tmp_db, source_id=src)
    link_evidence(tmp_db, claim_id=claim, evidence_id=sup, relationship="supports")
    link_evidence(tmp_db, claim_id=claim, evidence_id=con, relationship="contradicts")
    rows = {r["id"]: r for r in get_evidence_for_claim(tmp_db, claim)}
    assert rows[sup]["supports_claim"] == 1
    assert rows[con]["supports_claim"] == 0
    assert rows[sup]["relationship"] == "supports"


def test_unknown_relationship_rejected(tmp_db, src, claim):
    ev = create_evidence(tmp_db, source_id=src)
    with pytest.raises(EvidenceError, match="unknown relationship"):
        link_evidence(tmp_db, claim_id=claim, evidence_id=ev, relationship="proves")


def test_strength_scoring(tmp_db, src):
    strong = evidence_strength(
        {
            "source_quality": 5,
            "primary_source": True,
            "independence": 5,
            "directness": 5,
            "corroboration": 5,
            "contradiction": 0,
            "recency": 5,
        }
    )
    weak = evidence_strength(
        {
            "source_quality": 1,
            "primary_source": False,
            "independence": 1,
            "directness": 1,
            "corroboration": 0,
            "contradiction": 0,
            "recency": 1,
        }
    )
    assert 0.5 < strong <= 1.0
    assert 0.0 <= weak < 0.4
    contradicted = evidence_strength(
        {
            "source_quality": 5,
            "primary_source": True,
            "independence": 5,
            "directness": 5,
            "corroboration": 0,
            "contradiction": 5,
            "recency": 5,
        }
    )
    assert contradicted < strong


def test_update_strengths(tmp_db, src):
    eid = create_evidence(
        tmp_db,
        source_id=src,
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
    n = update_strengths(tmp_db)
    assert n == 1
    row = tmp_db.execute("SELECT strength FROM evidence WHERE id = ?", (eid,)).fetchone()
    assert row["strength"] > 0.5


def test_missing_evidence_summary(tmp_db, src, claim):
    sup = create_evidence(tmp_db, source_id=src, dimensions={"primary_source": True})
    link_evidence(tmp_db, claim_id=claim, evidence_id=sup, relationship="supports")
    gaps = missing_evidence(tmp_db, claim)
    assert gaps["supporting"] == 1
    assert gaps["has_primary_support"] is True
    assert gaps["contradicting"] == 0


def test_json_dimensions_roundtrip(tmp_db, src):
    eid = create_evidence(tmp_db, source_id=src, dimensions={"source_quality": 3})
    row = tmp_db.execute("SELECT dimensions_json FROM evidence WHERE id = ?", (eid,)).fetchone()
    assert json.loads(row["dimensions_json"]) == {"source_quality": 3}
