"""Corporate, legal and alternatives module tests (Phases 4-6)."""

from __future__ import annotations

import pytest
from app.claims import create_claim, create_organization
from app.evidence import create_evidence
from app.review import LEGAL_CHECKLIST, submit_review
from app.sources import create_source
from modules.alternatives import (
    CATEGORIES,
    alternative_score,
    create_alternative,
    dependency_map,
    iter_alternatives,
    migration_guide_fields,
)
from modules.corporate import (
    CorporateError,
    add_company_statement,
    claims_for_relationship,
    company_directory,
    create_relationship,
    relationship_summary,
    relationship_timeline,
)
from modules.international_law import (
    LawError,
    create_legal_document,
    documents_for_claim,
    get_document,
    iter_documents,
)
from modules.international_law import (
    link_claim as link_legal_claim,
)


@pytest.fixture()
def src(tmp_db):
    return create_source(
        tmp_db, url="https://s.example/1", title="S1", source_type="news", content_text="x"
    )


@pytest.fixture()
def company(tmp_db):
    return create_organization(tmp_db, name="ExampleCorp", org_type="company")


# ---------------------------------------------------------------------------
# Phase 4 — international law
# ---------------------------------------------------------------------------


def _mk_legal(tmp_db, src, **kw):
    defaults = dict(
        body="ICJ",
        case_or_document="Case X",
        document_type="provisional_measure",
        finding="The Court indicated certain provisional measures.",
        does_not_establish="This is not a final judgment on the merits.",
        source_id=src,
        doc_date="2024-01-26",
    )
    defaults.update(kw)
    return create_legal_document(tmp_db, **defaults)


def test_legal_document_requires_negation(tmp_db, src):
    with pytest.raises(LawError, match="does_not_establish"):
        _mk_legal(tmp_db, src, does_not_establish="  ")


def test_legal_document_requires_valid_type(tmp_db, src):
    with pytest.raises(LawError, match="document_type"):
        _mk_legal(tmp_db, src, document_type="final_truth")


def test_legal_document_requires_valid_body(tmp_db, src):
    with pytest.raises(LawError, match="body"):
        _mk_legal(tmp_db, src, body="Wizengamot")


def test_legal_document_requires_existing_source(tmp_db):
    with pytest.raises(LawError, match="source"):
        _mk_legal(tmp_db, "SRC-2026-9999")


def test_legal_document_defaults_pending(tmp_db, src):
    lid = _mk_legal(tmp_db, src)
    row = get_document(tmp_db, lid)
    assert row is not None
    assert row["review_status"] == "pending"
    assert row["document_type"] == "provisional_measure"
    assert lid in [r["id"] for r in iter_documents(tmp_db, body="ICJ")]


def test_legal_claim_crosslink(tmp_db, src):
    lid = _mk_legal(tmp_db, src)
    cid = create_claim(tmp_db, claim_text="The court acted.", speaker="S", source_id=src)
    link_legal_claim(tmp_db, claim_id=cid, legal_document_id=lid)
    docs = documents_for_claim(tmp_db, cid)
    assert [d["id"] for d in docs] == [lid]
    assert docs[0]["source_title"] == "S1"
    with pytest.raises(LawError, match="does not exist"):
        link_legal_claim(tmp_db, claim_id="CLM-2026-9999", legal_document_id=lid)


def test_legal_review_checklist_enforced(tmp_db, src):
    from app.review import ReviewError

    lid = _mk_legal(tmp_db, src)
    with pytest.raises(ReviewError, match="legal-document approval"):
        submit_review(
            tmp_db,
            subject_type="legal_document",
            subject_id=lid,
            reviewer="r",
            decision="approve",
            checklist={},
        )
    full = {k: True for k in LEGAL_CHECKLIST}
    submit_review(
        tmp_db,
        subject_type="legal_document",
        subject_id=lid,
        reviewer="r",
        decision="approve",
        checklist=full,
    )
    row = get_document(tmp_db, lid)
    assert row["review_status"] == "approved"
    assert row["last_reviewed"]


def test_legal_publication_requires_approval(tmp_db, src):
    from app.review import ReviewError, record_publication

    lid = _mk_legal(tmp_db, src)
    with pytest.raises(ReviewError, match="approved"):
        record_publication(tmp_db, subject_type="legal_document", subject_id=lid, format="web_page")
    full = {k: True for k in LEGAL_CHECKLIST}
    submit_review(
        tmp_db,
        subject_type="legal_document",
        subject_id=lid,
        reviewer="r",
        decision="approve",
        checklist=full,
    )
    pid = record_publication(
        tmp_db, subject_type="legal_document", subject_id=lid, format="web_page"
    )
    assert pid.startswith("PUB-")


# ---------------------------------------------------------------------------
# Phase 5 — corporate accountability
# ---------------------------------------------------------------------------


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


def test_relationship_timeline_ordered(tmp_db, src, company):
    ev = create_evidence(tmp_db, source_id=src, excerpt="contract")
    create_relationship(
        tmp_db,
        company_org_id=company,
        service="cloud",
        customer="gov",
        classification="documented_contract",
        start_date="2021-06-01",
        end_date="2023-01-31",
        evidence_ids=[ev],
        company_response="Contract ended.",
    )
    add_company_statement(
        tmp_db,
        organization_id=company,
        statement_text="We are reviewing.",
        statement_type="clarification",
        statement_date="2022-03-15",
    )
    timeline = relationship_timeline(tmp_db, company)
    dates = [e["date"] for e in timeline if e["date"]]
    assert dates == sorted(dates)
    kinds = {e["kind"] for e in timeline}
    assert kinds == {"relationship", "statement", "response"}
    assert any("relationship start" in e["label"] for e in timeline)
    assert any("relationship end" in e["label"] for e in timeline)


def test_company_directory_groups_relationships(tmp_db, src, company):
    ev = create_evidence(tmp_db, source_id=src, excerpt="e")
    r1 = create_relationship(
        tmp_db,
        company_org_id=company,
        service="cloud",
        customer="gov",
        classification="documented_contract",
        evidence_ids=[ev],
    )
    create_relationship(
        tmp_db,
        company_org_id=company,
        service="email",
        customer="agency",
        classification="reported_relationship",
        evidence_ids=[ev],
    )
    # default view shows only approved relationships
    assert company_directory(tmp_db) == []
    submit_review(
        tmp_db,
        subject_type="relationship",
        subject_id=r1,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    directory = company_directory(tmp_db)
    assert len(directory) == 1
    assert directory[0]["company"] == "ExampleCorp"
    assert directory[0]["relationships"] == [r1]
    # unfiltered view for reviewers
    everything = company_directory(tmp_db, approved_only=False)
    assert len(everything[0]["relationships"]) == 2


def test_claims_for_relationship_approved_only(tmp_db, src, company):
    ev = create_evidence(tmp_db, source_id=src, excerpt="e")
    rid = create_relationship(
        tmp_db,
        company_org_id=company,
        service="cloud",
        customer="gov",
        classification="documented_contract",
        evidence_ids=[ev],
    )
    create_claim(
        tmp_db,
        claim_text="Company operates the service.",
        speaker="S",
        source_id=src,
        organization_id=company,
    )
    approved = create_claim(
        tmp_db,
        claim_text="Company described the contract.",
        speaker="S",
        source_id=src,
        organization_id=company,
    )
    submit_review(
        tmp_db,
        subject_type="claim",
        subject_id=approved,
        reviewer="r",
        decision="approve",
        checklist={},
    )
    claims = claims_for_relationship(tmp_db, rid)
    assert [c["id"] for c in claims] == [approved]


# ---------------------------------------------------------------------------
# Phase 6 — alternatives
# ---------------------------------------------------------------------------


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


def test_alternative_score_validated(tmp_db):
    with pytest.raises(ValueError, match="0-5"):
        create_alternative(
            tmp_db,
            product="X",
            alternative="Y",
            category="cloud_storage",
            score={"open_source": 7},
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
        score={"open_source": 5, "security": 4},
        migration_notes="Export via WebDAV.",
        limitations="No office suite.",
    )
    rows = iter_alternatives(tmp_db)
    assert [r["id"] for r in rows] == [aid]
    assert rows[0]["self_hosting_available"] == 1
    assert alternative_score(rows[0]) == 4.5


def test_migration_guide_fields(tmp_db):
    aid = create_alternative(
        tmp_db,
        product="ExampleDrive",
        company="ExampleCorp",
        category="cloud_storage",
        alternative="Nextcloud",
        migration_difficulty="hard",
        self_hosting_available=True,
        score={"active_development": 5},
        migration_notes="rsync-based",
        limitations="Sharing links differ",
    )
    row = next(r for r in iter_alternatives(tmp_db) if r["id"] == aid)
    guide = migration_guide_fields(row)
    assert guide["replaces"] == "ExampleDrive"
    assert guide["data_migration"] == "rsync-based"
    assert guide["limitations"] == "Sharing links differ"
    assert guide["project_health"] == 5
    assert guide["score"] == 5.0


def test_dependency_map_groups_products(tmp_db):
    create_alternative(
        tmp_db,
        product="ExampleDrive",
        company="ExampleCorp",
        category="cloud_storage",
        alternative="Nextcloud",
        migration_difficulty="moderate",
        score={"open_source": 5},
    )
    create_alternative(
        tmp_db,
        product="ExampleDrive",
        company="ExampleCorp",
        category="cloud_storage",
        alternative="local NAS",
        migration_difficulty="hard",
        score={"open_source": 3},
    )
    dmap = dependency_map(tmp_db, approved_only=False)
    assert len(dmap) == 1
    assert len(dmap[0]["alternatives"]) == 2
    scores = [a["score"] for a in dmap[0]["alternatives"]]
    assert sorted(scores) == [3.0, 5.0]


def test_alternative_score_empty(tmp_db):
    create_alternative(tmp_db, product="X", alternative="Y", category="email")
    row = iter_alternatives(tmp_db)[0]
    assert alternative_score(row) == 0.0


def test_categories_cover_spec(tmp_db):
    # agentodo §15 category list is represented
    assert "cloud_storage" in CATEGORIES
    assert "password_management" in CATEGORIES
    assert "ai_inference" in CATEGORIES
