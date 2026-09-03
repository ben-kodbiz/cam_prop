"""Search tests: keyword + metadata hybrid."""

from __future__ import annotations

import pytest
from app.claims import create_claim
from app.search import SearchHit, search
from app.sources import create_source


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


def test_keyword_search(tmp_db, src):
    a = create_claim(tmp_db, claim_text="The airstrike occurred.", speaker="A", source_id=src)
    create_claim(tmp_db, claim_text="Unrelated statement about trade.", speaker="B", source_id=src)
    hits = search(tmp_db, "airstrike")
    ids = [h.claim_id for h in hits]
    assert a in ids


def test_metadata_filter(tmp_db, src):
    a = create_claim(tmp_db, claim_text="One claim.", speaker="A", source_id=src, topic="t1")
    create_claim(tmp_db, claim_text="Two claim.", speaker="B", source_id=src, topic="t2")
    hits = search(tmp_db, "", topic="t1")
    assert [h.claim_id for h in hits] == [a]
    assert hits[0].matched_by == "metadata"


def test_combined_keyword_and_metadata(tmp_db, src):
    create_claim(tmp_db, claim_text="Airstrike evidence.", speaker="A", source_id=src, topic="t1")
    create_claim(
        tmp_db, claim_text="Airstrike other topic.", speaker="B", source_id=src, topic="t2"
    )
    hits = search(tmp_db, "airstrike", topic="t2")
    assert len(hits) == 1
    assert hits[0].matched_by == "keyword"


def test_status_filter(tmp_db, src):
    a = create_claim(tmp_db, claim_text="Status test.", speaker="A", source_id=src)
    tmp_db.execute("UPDATE claims SET status = 'disputed' WHERE id = ?", (a,))
    hits = search(tmp_db, "", status="disputed")
    assert [h.claim_id for h in hits] == [a]


def test_search_hit_shape(tmp_db, src):
    create_claim(tmp_db, claim_text="Shape test.", speaker="A", source_id=src)
    hits = search(tmp_db, "shape")
    assert isinstance(hits[0], SearchHit)
    assert hits[0].status in ("unknown", "supported", "disputed")
