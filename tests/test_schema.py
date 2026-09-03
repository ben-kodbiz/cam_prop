"""Schema tests: tables, constraints, indexes."""

from __future__ import annotations

import sqlite3

import pytest
from app.db import connect, init_db


def test_init_db_creates_all_tables(tmp_path):
    init_db(tmp_path / "a.db")
    init_db(tmp_path / "a.db")  # idempotent
    conn = connect(tmp_path / "a.db")
    try:
        names = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        expected = {
            "sources",
            "claims",
            "evidence",
            "claim_evidence",
            "organizations",
            "people",
            "events",
            "corporate_relationships",
            "company_statements",
            "alternatives",
            "reviews",
            "publications",
            "audit_log",
            "claims_fts",
        }
        assert expected <= names
    finally:
        conn.close()


def test_claim_status_check_constraint(tmp_db):
    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute(
            "INSERT INTO claims (id, claim_text, normalized_claim, speaker,"
            " speaker_type, discovered_at, status, created_at, updated_at)"
            " VALUES ('X', 'x', 'x', 's', 'other', '2024', 'bogus', '2024', '2024')"
        )
        tmp_db.commit()


def test_foreign_keys_enforced(tmp_db):
    tmp_db.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        tmp_db.execute(
            "INSERT INTO evidence (id, source_id, evidence_type, created_at, updated_at)"
            " VALUES ('E', 'NOPE', 'document', '2024', '2024')"
        )


def test_fts_table_searchable(tmp_db):
    tmp_db.execute(
        "INSERT INTO claims_fts (claim_id, claim_text, normalized_claim) VALUES"
        " ('C1', 'airstrike occurred', 'airstrike occurred')"
    )
    rows = tmp_db.execute(
        "SELECT claim_id FROM claims_fts WHERE claims_fts MATCH 'airstrike'"
    ).fetchall()
    assert [r["claim_id"] for r in rows] == ["C1"]
