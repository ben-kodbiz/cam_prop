"""Export tests: only approved content reaches the static site."""

from __future__ import annotations

import json

from app.claims import create_claim
from app.evidence import create_evidence, link_evidence
from app.export import export_all
from app.review import submit_review
from app.sources import create_source


def _setup(tmp_db):
    src = create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )
    approved = create_claim(tmp_db, claim_text="Approved claim.", speaker="A", source_id=src)
    pending = create_claim(tmp_db, claim_text="Pending claim.", speaker="B", source_id=src)
    ev = create_evidence(tmp_db, source_id=src, excerpt="e")
    link_evidence(tmp_db, claim_id=approved, evidence_id=ev, relationship="supports")
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=approved,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    return src, approved, pending


def test_export_writes_json(tmp_db, tmp_path):
    _src, approved, pending = _setup(tmp_db)
    tmp_db.commit()
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    counts = export_all(db_path, tmp_path / "out")
    assert counts["claims.json"] == 1
    data = json.loads((tmp_path / "out" / "claims.json").read_text())
    assert data[0]["id"] == approved
    assert pending not in [c["id"] for c in data]


def test_export_includes_sources_of_evidence(tmp_db, tmp_path):
    src, _approved, _pending = _setup(tmp_db)
    tmp_db.commit()
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    sources = json.loads((tmp_path / "out" / "sources.json").read_text())
    assert [s["id"] for s in sources] == [src]


def test_export_evidence_attached(tmp_db, tmp_path):
    _, _approved, _pending = _setup(tmp_db)
    tmp_db.commit()
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    data = json.loads((tmp_path / "out" / "claims.json").read_text())
    assert data[0]["evidence"][0]["relationship"] == "supports"


def test_export_site_data(tmp_db, tmp_path):
    from app.export import export_site_data

    _setup(tmp_db)
    tmp_db.commit()
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    counts = export_site_data(db_path, tmp_path / "web")
    assert (tmp_path / "web" / "data" / "claims.json").is_file()
    assert counts["claims.json"] == 1
