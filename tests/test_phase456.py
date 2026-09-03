"""Phase 4-6 integration: migrations, export enrichment, seed fixtures."""

from __future__ import annotations

import json

from app.db import connect, init_db
from app.export import export_all
from app.seed import seed


def test_migration_rebuilds_old_reviews_table(tmp_path):
    """A DB created before legal_document existed accepts it after migration."""
    db = tmp_path / "old.db"
    # simulate a pre-Phase-4 reviews table without 'legal_document' in CHECK
    conn = connect(db)
    conn.executescript(
        """CREATE TABLE reviews (
            id TEXT PRIMARY KEY,
            subject_type TEXT NOT NULL
                CHECK (subject_type IN ('claim', 'relationship', 'statement', 'alternative')),
            subject_id TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            decision TEXT NOT NULL,
            checklist_json TEXT NOT NULL DEFAULT '{}',
            notes TEXT,
            reviewed_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );"""
    )
    conn.execute(
        "INSERT INTO reviews (id, subject_type, subject_id, reviewer, decision,"
        " reviewed_at, created_at) VALUES ('REV-2026-0001', 'claim', 'CLM-2026-0001',"
        " 'r', 'approve', '2026-01-01', '2026-01-01')"
    )
    conn.commit()
    conn.close()

    init_db(db)  # runs schema + migrations
    conn = connect(db)
    # old rows preserved
    n = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    assert n == 1
    # new subject_type values are accepted now
    conn.execute(
        "INSERT INTO reviews (id, subject_type, subject_id, reviewer, decision,"
        " reviewed_at, created_at) VALUES ('REV-2026-0002', 'legal_document',"
        " 'LGL-2026-0001', 'r', 'approve', '2026-01-02', '2026-01-02')"
    )
    conn.commit()
    conn.close()


def test_migration_preserves_alternatives_columns(tmp_path):
    db = tmp_path / "old2.db"
    conn = connect(db)
    conn.executescript(
        """CREATE TABLE alternatives (
            id TEXT PRIMARY KEY,
            product TEXT NOT NULL,
            company TEXT,
            category TEXT NOT NULL,
            alternative TEXT NOT NULL,
            alternative_license TEXT,
            alternative_hosting TEXT,
            self_hosting_available INTEGER,
            migration_difficulty TEXT,
            privacy_notes TEXT,
            replaces_url TEXT,
            alternative_url TEXT,
            source_ids_json TEXT NOT NULL DEFAULT '[]',
            notes TEXT,
            review_status TEXT NOT NULL DEFAULT 'pending',
            revision INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );"""
    )
    conn.execute(
        "INSERT INTO alternatives (id, product, category, alternative, review_status,"
        " revision, created_at, updated_at)"
        " VALUES ('ALT-2026-0001', 'X', 'email', 'Y', 'pending', 1, '2026', '2026')"
    )
    conn.commit()
    conn.close()

    init_db(db)
    conn = connect(db)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(alternatives)")}
    assert {"score_json", "migration_notes", "limitations"} <= cols
    row = conn.execute("SELECT * FROM alternatives WHERE id = 'ALT-2026-0001'").fetchone()
    assert row["product"] == "X"
    assert json.loads(row["score_json"]) == {}
    conn.close()


def _seeded(tmp_db, tmp_path):
    ids = seed(tmp_db, archive_dir=tmp_path / "archive")
    tmp_db.commit()
    return ids


def test_export_includes_legal(tmp_db, tmp_path):
    ids = _seeded(tmp_db, tmp_path)
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    counts = export_all(db_path, tmp_path / "out")
    assert counts["legal.json"] == 1
    legal = json.loads((tmp_path / "out" / "legal.json").read_text())
    assert legal[0]["id"] == ids["legal_document"]
    assert legal[0]["document_type"] == "provisional_measure"
    assert "does_not_establish" in legal[0]
    assert legal[0]["claims"] == [ids["claim_reviewed"]]


def test_export_claim_has_legal_documents(tmp_db, tmp_path):
    ids = _seeded(tmp_db, tmp_path)
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    claims = json.loads((tmp_path / "out" / "claims.json").read_text())
    claim = next(c for c in claims if c["id"] == ids["claim_reviewed"])
    assert claim["legal_documents"][0]["id"] == ids["legal_document"]
    assert claim["legal_documents"][0]["does_not_establish"]


def test_export_companies_have_timeline(tmp_db, tmp_path):
    ids = _seeded(tmp_db, tmp_path)
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    companies = json.loads((tmp_path / "out" / "companies.json").read_text())
    assert len(companies) == 1
    entry = companies[0]
    assert entry["id"] == ids["corporate_relationship"]
    kinds = {e["kind"] for e in entry["timeline"]}
    assert "relationship" in kinds
    assert "statement" in kinds


def test_export_alternatives_have_score_and_guide(tmp_db, tmp_path):
    ids = _seeded(tmp_db, tmp_path)
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    alts = json.loads((tmp_path / "out" / "alternatives.json").read_text())
    assert len(alts) == 1
    a = alts[0]
    assert a["id"] == ids["alternative"]
    assert a["score"] > 3.5
    assert a["migration_guide"]["data_migration"].startswith("SEED")
    assert a["score_dimensions"]["open_source"] == 5


def test_export_includes_alternative_sources(tmp_db, tmp_path):
    _seeded(tmp_db, tmp_path)
    db_path = tmp_db.execute("PRAGMA database_list").fetchone()["file"]
    export_all(db_path, tmp_path / "out")
    sources = json.loads((tmp_path / "out" / "sources.json").read_text())
    # SEED uses the corp source on the alternative; ensure it appears
    ids = [s["id"] for s in sources]
    assert any(s["source_type"] == "company_statement" for s in sources)
    assert all(i for i in ids)
