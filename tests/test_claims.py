"""Claim tests: creation, dedup, splitting, FTS sync, invariants."""

from __future__ import annotations

import pytest
from app.claims import (
    ClaimError,
    DuplicateClaimError,
    create_claim,
    create_event,
    find_duplicates,
    get_claim,
    search_claims,
    set_status,
    split_compound_claim,
)
from app.evidence import create_evidence, link_evidence
from app.review import submit_review
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


@pytest.fixture()
def claim(tmp_db, src):
    return create_claim(
        tmp_db, claim_text="The airstrike occurred.", speaker="Ministry", source_id=src
    )


def test_create_claim_defaults_unknown(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="A claim.", speaker="X", source_id=src)
    row = get_claim(tmp_db, cid)
    assert row["status"] == "unknown"
    assert row["review_status"] == "pending"
    assert row["revision"] == 1


def test_empty_claim_rejected(tmp_db, src):
    with pytest.raises(ClaimError, match="empty"):
        create_claim(tmp_db, claim_text="  ", speaker="X", source_id=src)


def test_missing_source_rejected(tmp_db):
    with pytest.raises(ClaimError, match="source"):
        create_claim(tmp_db, claim_text="A.", speaker="X", source_id="SRC-2026-9999")


def test_duplicate_claim_detected(tmp_db, src, claim):
    with pytest.raises(DuplicateClaimError):
        create_claim(tmp_db, claim_text="The  AIRSTRIKE occurred!", speaker="Y", source_id=src)
    rows = find_duplicates(tmp_db, "the airstrike   occurred")
    assert len(rows) == 1


def test_split_compound_claim():
    parts = split_compound_claim(
        "Weapons were delivered because the contract was signed,"
        " and therefore the attack was justified."
    )
    assert len(parts) >= 3
    single = split_compound_claim("One simple factual statement.")
    assert single == ["One simple factual statement."]


def test_fts_synced_on_create(tmp_db, src, claim):
    rows = search_claims(tmp_db, "airstrike")
    assert any(r["id"] == claim for r in rows)


def test_status_requires_evidence(tmp_db, src, claim):
    with pytest.raises(Exception, match="invariant violation"):
        set_status(tmp_db, claim, "supported", actor="test", override=True)


def test_status_requires_approval(tmp_db, src, claim):
    ev = create_evidence(
        tmp_db, source_id=src, evidence_type="document", dimensions={"source_quality": 4}
    )
    link_evidence(tmp_db, claim_id=claim, evidence_id=ev, relationship="supports")
    with pytest.raises(Exception, match="not approved"):
        set_status(tmp_db, claim, "supported", actor="agent")
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=claim,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    set_status(tmp_db, claim, "supported", actor="r", override=True)
    assert get_claim(tmp_db, claim)["status"] == "supported"


def test_contradicted_requires_contradicting_evidence(tmp_db, src, claim):
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=claim,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    ev = create_evidence(
        tmp_db, source_id=src, evidence_type="document", dimensions={"source_quality": 4}
    )
    link_evidence(tmp_db, claim_id=claim, evidence_id=ev, relationship="supports")
    with pytest.raises(Exception, match="invariant violation"):
        set_status(tmp_db, claim, "contradicted", actor="r", override=True)
    ev2 = create_evidence(tmp_db, source_id=src, evidence_type="document")
    link_evidence(tmp_db, claim_id=claim, evidence_id=ev2, relationship="contradicts")
    set_status(tmp_db, claim, "contradicted", actor="r", override=True)


def test_unknown_stays_unknown_without_evidence(tmp_db, src, claim):
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=claim,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    set_status(tmp_db, claim, "unknown", actor="r", override=True)
    assert get_claim(tmp_db, claim)["status"] == "unknown"


def test_event_link(tmp_db, src, claim):
    eid = create_event(tmp_db, title="Event")
    from app.claims import link_event

    link_event(tmp_db, claim, eid)
    assert get_claim(tmp_db, claim)["event_id"] == eid
