"""Seeds the database with minimal fixture data for local development.

All seed content is PLACEHOLDER data clearly marked as such — it exists to
exercise the pipeline and tests, never to make real-world assertions.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.claims import (
    create_claim,
    create_event,
    create_organization,
    link_event,
)
from app.evidence import create_evidence, evidence_strength, link_evidence
from app.review import REVIEW_CHECKLIST, submit_review
from app.sources import create_source

SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "seed"


def seed(conn: sqlite3.Connection, archive_dir: Path | None = None) -> dict[str, str]:
    """Create fixture sources, claims, evidence, one approved claim."""
    ids: dict[str, str] = {}

    # --- sources -----------------------------------------------------------
    icj = create_source(
        conn,
        url="https://www.icj-cij.org/sites/default/files/case-related/186/186-20240126-ord-01-00-en.pdf",
        title="Application of the Genocide Convention (Order on Provisional Measures)",
        source_type="icj",
        publisher="International Court of Justice",
        published_at="2024-01-26",
        content_text="SEED DATA: provisional measures order text placeholder.",
    )
    news = create_source(
        conn,
        url="https://example.org/news/example-news-article?utm_source=rss",
        title="SEED: Example news article about a contested statement",
        source_type="news",
        publisher="Example News",
        published_at="2024-02-01",
        content_text="SEED DATA: example news article body placeholder.",
    )
    corp = create_source(
        conn,
        url="https://example.com/investors/contract-announcement.html",
        title="SEED: ExampleCorp contract announcement",
        source_type="company_statement",
        publisher="ExampleCorp",
        published_at="2023-06-15",
        content_text="SEED DATA: company statement placeholder.",
    )
    ids["icj_source"] = icj
    ids["news_source"] = news
    ids["corp_source"] = corp

    # --- organizations / people / events ----------------------------------
    gov = create_organization(conn, name="SEED Government Ministry", org_type="government")
    company = create_organization(conn, name="ExampleCorp", org_type="company")
    ids["gov_org"] = gov
    ids["company_org"] = company

    event = create_event(
        conn,
        title="SEED: Example event",
        description="Placeholder event for fixture claims.",
        occurred_on="2024-01-15",
        event_type="other",
    )
    ids["event"] = event

    # --- claims -------------------------------------------------------------
    claim_reviewed = create_claim(
        conn,
        claim_text="SEED: The court issued provisional measures in the case.",
        speaker="SEED Government Ministry",
        speaker_type="government",
        organization_id=gov,
        source_id=news,
        published_at="2024-02-02",
        topic="international_law",
        importance="high",
    )
    claim_pending = create_claim(
        conn,
        claim_text="SEED: ExampleCorp provides cloud services under a government contract.",
        speaker="ExampleCorp",
        speaker_type="company",
        organization_id=company,
        source_id=corp,
        published_at="2023-06-15",
        topic="corporate_allegations",
        importance="medium",
    )
    claim_unknown = create_claim(
        conn,
        claim_text="SEED: This claim has no evidence at all.",
        speaker="SEED Speaker",
        speaker_type="individual",
        source_id=news,
        published_at="2024-02-03",
        topic=None,
        importance="low",
    )
    link_event(conn, claim_reviewed, event)
    ids["claim_reviewed"] = claim_reviewed
    ids["claim_pending"] = claim_pending
    ids["claim_unknown"] = claim_unknown

    # --- evidence ------------------------------------------------------------
    ev1 = create_evidence(
        conn,
        source_id=icj,
        evidence_type="ruling",
        excerpt="SEED EXCERPT: The Court indicates provisional measures.",
        section="Operative clause",
        context="Order indicating provisional measures.",
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
    ev2 = create_evidence(
        conn,
        source_id=corp,
        evidence_type="document",
        excerpt="SEED EXCERPT: We are proud to announce our new government contract.",
        context="Company announcement of a contract.",
        dimensions={
            "source_quality": 4,
            "primary_source": True,
            "independence": 1,
            "directness": 5,
            "corroboration": 2,
            "contradiction": 0,
            "recency": 3,
        },
    )
    ids["evidence_icj"] = ev1
    ids["evidence_corp"] = ev2

    link_evidence(conn, claim_id=claim_reviewed, evidence_id=ev1, relationship="supports")
    link_evidence(conn, claim_id=claim_pending, evidence_id=ev2, relationship="supports")

    # recompute strengths
    import json as _json

    for row in conn.execute("SELECT id, dimensions_json FROM evidence").fetchall():
        dims = _json.loads(row["dimensions_json"] or "{}")
        conn.execute(
            "UPDATE evidence SET strength = ? WHERE id = ?",
            (evidence_strength(dims), row["id"]),
        )

    # --- review the first claim ---------------------------------------------
    checklist = {k: True for k in REVIEW_CHECKLIST}
    submit_review(
        conn,
        subject_type="claim",
        subject_id=claim_reviewed,
        reviewer="seed-reviewer",
        decision="approve",
        checklist=checklist,
        notes="SEED fixture review.",
    )
    from app.claims import set_status

    set_status(
        conn,
        claim_reviewed,
        "supported",
        actor="seed-reviewer",
        override=True,
        reason="SEED: provisional measures order directly supports the claim",
    )
    conn.execute("UPDATE claims SET confidence = 0.9 WHERE id = ?", (claim_reviewed,))

    # --- Phase 4: legal document + cross-link --------------------------------
    from modules.international_law import create_legal_document
    from modules.international_law import link_claim as link_legal

    from app.review import LEGAL_CHECKLIST

    legal_id = create_legal_document(
        conn,
        body="ICJ",
        case_or_document="SEED: Example Provisional Measures Order",
        document_type="provisional_measure",
        finding="SEED: The Court indicated certain provisional measures.",
        does_not_establish="SEED: This order is not a judgment on the merits.",
        source_id=icj,
        jurisdiction="global",
        doc_date="2024-01-26",
    )
    link_legal(conn, claim_id=claim_reviewed, legal_document_id=legal_id)
    submit_review(
        conn,
        subject_type="legal_document",
        subject_id=legal_id,
        reviewer="seed-reviewer",
        decision="approve",
        checklist={k: True for k in LEGAL_CHECKLIST},
        notes="SEED fixture legal review.",
    )
    ids["legal_document"] = legal_id

    # --- Phase 5: corporate relationship + statement --------------------------
    from modules.corporate import (
        add_company_statement,
        create_relationship,
    )

    corp_rel = create_relationship(
        conn,
        company_org_id=company,
        service="SEED: cloud infrastructure",
        customer="SEED: government entity",
        classification="documented_contract",
        contract_ref="SEED-CONTRACT-1",
        evidence_ids=[ev2],
        company_response="SEED: We comply with all applicable laws.",
        start_date="2023-06-01",
        status_notes="SEED fixture relationship.",
    )
    add_company_statement(
        conn,
        organization_id=company,
        statement_text="SEED: We confirm the contract exists and comply with all laws.",
        statement_type="confirmation",
        statement_date="2023-06-20",
        relates_to_relationship_id=corp_rel,
    )
    submit_review(
        conn,
        subject_type="relationship",
        subject_id=corp_rel,
        reviewer="seed-reviewer",
        decision="approve",
        checklist={},
        notes="SEED fixture relationship review.",
    )
    ids["corporate_relationship"] = corp_rel

    # --- Phase 6: alternatives ------------------------------------------------
    from modules.alternatives import create_alternative

    alt1 = create_alternative(
        conn,
        product="SEED ExampleDrive",
        company="ExampleCorp",
        category="cloud_storage",
        alternative="SEED Nextcloud",
        alternative_license="AGPL-3.0",
        alternative_hosting="self-hosted",
        self_hosting_available=True,
        migration_difficulty="moderate",
        privacy_notes="SEED: self-hosted storage keeps data under user control.",
        alternative_url="https://example.org/nextcloud",
        source_ids=[corp],
        score={
            "open_source": 5,
            "self_hostable": 5,
            "active_development": 4,
            "security": 4,
            "documentation": 4,
            "migration": 3,
            "cost": 5,
            "lock_in": 5,
            "privacy": 5,
            "community": 4,
        },
        migration_notes="SEED: export data via WebDAV, import into instance.",
        limitations="SEED: sharing features differ from the commercial product.",
    )
    submit_review(
        conn,
        subject_type="alternative",
        subject_id=alt1,
        reviewer="seed-reviewer",
        decision="approve",
        checklist={},
        notes="SEED fixture alternative review.",
    )
    ids["alternative"] = alt1

    ids["reviewer"] = "seed-reviewer"
    return ids
