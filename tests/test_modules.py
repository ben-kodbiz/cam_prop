"""Corporate, legal and alternatives module tests."""

from __future__ import annotations

import pytest
from app.evidence import create_evidence
from app.sources import create_source
from modules.alternatives import create_alternative, iter_alternatives
from modules.corporate import (
    CorporateError,
    add_company_statement,
    create_relationship,
    relationship_summary,
)
from modules.international_law import LawError, create_legal_record, legal_records


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


@pytest.fixture()
def company(tmp_db):
    from app.claims import create_organization

    return create_organization(tmp_db, name="ExampleCorp", org_type="company")


def test_relationship_requires_existing_org(tmp_db, src):
    with pytest.raises(CorporateError, match="organization"):
        create_relationship(tmp_db, company_org_id="ORG-2026-9999", service="cloud", customer="gov")


def test_relationship_evidence_must_exist(tmp_db, company):
    with pytest.raises(CorporateError, match="evidence"):
        create_relationship(
            tmp_db,
            company_org_id=company,
            service="cloud",
            customer="gov",
            evidence_ids=["EVD-2026-9999"],
        )


def test_relationship_summary_answers_accountability_questions(tmp_db, src, company):
    ev = create_evidence(tmp_db, source_id=src, excerpt="contract")
    rid = create_relationship(
        tmp_db,
        company_org_id=company,
        service="cloud infrastructure",
        customer="government entity",
        classification="documented_service",
        contract_ref="GS-123",
        evidence_ids=[ev],
        company_response="We comply with all laws.",
    )
    add_company_statement(
        tmp_db,
        organization_id=company,
        statement_text="We confirm the contract.",
        statement_type="confirmation",
        statement_date="2023-01-01",
        relates_to_relationship_id=rid,
    )
    s = relationship_summary(tmp_db, rid)
    assert s["company"] == "ExampleCorp"
    assert s["what_is_documented"] == "documented_service"
    assert len(s["evidence"]) == 1
    assert s["company_response"][0]["type"] == "confirmation"
    assert "contract_value" in s["unknowns"]


def test_legal_record_requires_does_not_establish(tmp_db, src):
    with pytest.raises(LawError, match="does_not_establish"):
        create_legal_record(
            tmp_db,
            body="ICJ",
            case_or_document="Case X",
            document_type="provisional_measure",
            date="2024-01-26",
            finding="The Court indicated provisional measures.",
            does_not_establish="",
            source_id=src,
        )


def test_legal_record_requires_valid_type(tmp_db, src):
    with pytest.raises(LawError, match="document_type"):
        create_legal_record(
            tmp_db,
            body="ICJ",
            case_or_document="Case X",
            document_type="final_truth",
            date="2024-01-26",
            finding="F",
            does_not_establish="not a judgment",
            source_id=src,
        )


def test_legal_record_created_as_high_impact(tmp_db, src):
    cid = create_legal_record(
        tmp_db,
        body="ICJ",
        case_or_document="Case X",
        document_type="provisional_measure",
        date="2024-01-26",
        finding="The Court indicated certain provisional measures.",
        does_not_establish="This is not a final judgment on the merits.",
        source_id=src,
    )
    row = tmp_db.execute("SELECT topic, importance FROM claims WHERE id = ?", (cid,)).fetchone()
    assert row["topic"] == "international_law"
    assert row["importance"] == "high"
    assert cid in [r["id"] for r in legal_records(tmp_db)]


def test_alternative_category_validated(tmp_db):
    with pytest.raises(ValueError, match="category"):
        create_alternative(tmp_db, product="X", alternative="Y", category="widgets")


def test_alternative_migration_difficulty_validated(tmp_db):
    with pytest.raises(ValueError, match="migration_difficulty"):
        create_alternative(
            tmp_db,
            product="X",
            alternative="Y",
            category="cloud_storage",
            migration_difficulty="trivial",
        )


def test_alternative_lifecycle(tmp_db):
    aid = create_alternative(
        tmp_db,
        product="ExampleDrive",
        company="ExampleCorp",
        category="cloud_storage",
        alternative="Nextcloud",
        alternative_license="AGPL-3.0",
        self_hosting_available=True,
        migration_difficulty="moderate",
    )
    rows = iter_alternatives(tmp_db)
    assert [r["id"] for r in rows] == [aid]
    assert rows[0]["self_hosting_available"] == 1
