"""Citation and reproducibility tests."""

from __future__ import annotations

import pytest
from app.citations import (
    citation_for_source,
    citations_for_claim,
    claim_reference,
    reproducibility_bundle,
    source_reference,
)
from app.claims import create_claim
from app.evidence import create_evidence, link_evidence
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db,
        url="https://s.example/1",
        title="Important Document",
        source_type="icj",
        publisher="ICJ",
        content_text="x",
    )


def test_citation_format(tmp_db, src):
    c = citation_for_source(tmp_db, src)
    assert c is not None
    text = c.format()
    assert "ICJ" in text
    assert src in text
    assert "https://s.example/1" in text


def test_claim_citations_ordered_by_tier(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Cite.", speaker="X", source_id=src)
    low_src = create_source(
        tmp_db,
        url="https://s.example/2",
        title="Social",
        source_type="social_media",
        content_text="x",
    )
    ev1 = create_evidence(tmp_db, source_id=low_src, excerpt="low tier quote")
    ev2 = create_evidence(tmp_db, source_id=src, excerpt="primary quote")
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev1, relationship="supports")
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev2, relationship="supports")
    cites = citations_for_claim(tmp_db, cid)
    assert cites[0].source_tier == 1
    assert cites[0].excerpt == "primary quote"


def test_stable_references():
    assert claim_reference("CLM-2026-0001") == "/claim/CLM-2026-0001/"
    assert source_reference("SRC-2026-0001") == "/source/SRC-2026-0001/"


def test_reproducibility_bundle(tmp_db, src):
    cid = create_claim(tmp_db, claim_text="Repro.", speaker="X", source_id=src)
    ev = create_evidence(tmp_db, source_id=src, excerpt="key excerpt")
    link_evidence(tmp_db, claim_id=cid, evidence_id=ev, relationship="supports")
    bundle = reproducibility_bundle(tmp_db, cid)
    assert bundle["claim_id"] == cid
    assert bundle["methodology_version"].startswith("open-evidence/")
    assert bundle["citations"][0]["source_id"] == src
    assert bundle["citations"][0]["excerpt"] == "key excerpt"


def test_bundle_missing_claim(tmp_db):
    with pytest.raises(ValueError, match="does not exist"):
        reproducibility_bundle(tmp_db, "CLM-2026-9999")
