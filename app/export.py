"""Export approved database content to static JSON for the frontend (agentodo §32).

Only approved, published subjects are exported — the public site is a
static mirror of reviewed content, nothing else.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ExportError(ValueError):
    pass


def _claim_to_dict(conn: sqlite3.Connection, row: sqlite3.Row, site_url: str) -> dict[str, Any]:
    from app.citations import claim_reference
    from app.evidence import get_evidence_for_claim
    from app.util import normalize_claim_text

    ev = get_evidence_for_claim(conn, row["id"])
    return {
        "id": row["id"],
        "claim_text": row["claim_text"],
        "speaker": row["speaker"],
        "speaker_type": row["speaker_type"],
        "published_at": row["published_at"],
        "status": row["status"],
        "confidence": row["confidence"],
        "topic": row["topic"],
        "importance": row["importance"],
        "last_reviewed": row["last_reviewed"],
        "revision": row["revision"],
        "url": claim_reference(row["id"]),
        "evidence": [
            {
                "evidence_id": e["id"],
                "source_id": e["source_id"],
                "relationship": e["relationship"],
                "publisher": e["publisher"],
                "title": e["title"],
                "url": e["canonical_url"],
                "excerpt": e["excerpt"],
                "page_number": e["page_number"],
                "section": e["section"],
                "source_tier": e["source_tier"],
                "published_at": e["published_at"],
                "strength": e["strength"],
            }
            for e in ev
        ],
        "explanation": row["explanation"],
        "translated_text": row["translated_text"],
        "original_language": row["original_language"],
        "search_text": normalize_claim_text(row["claim_text"]),
    }


def _source_to_dict(conn: sqlite3.Connection, source_id: str) -> dict[str, Any] | None:
    s = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    if s is None:
        return None
    return {
        "id": s["id"],
        "title": s["title"],
        "publisher": s["publisher"],
        "url": s["canonical_url"],
        "source_type": s["source_type"],
        "source_tier": s["source_tier"],
        "published_at": s["published_at"],
        "retrieved_at": s["retrieved_at"],
        "archive_path": s["archive_path"],
        "content_hash": s["content_hash"],
        "doc_kind": s["doc_kind"] or "url",
        "book_author": s["book_author"],
        "book_year": s["book_year"],
        "book_pages": s["book_pages"],
        "book_isbn": s["book_isbn"],
    }


def export_all(db_path: str | Path, out_dir: str | Path, *, site_url: str = "") -> dict[str, int]:
    """Write claims/sources/companies/alternatives/legal JSON for the site.

    Returns counts. Only approved claims / relationships / alternatives /
    legal documents are included; sources referenced by exported evidence,
    legal documents or book imports are included.
    """
    from modules.alternatives import alternative_score, migration_guide_fields
    from modules.corporate import relationship_timeline
    from modules.international_law import document_summary, documents_for_claim

    from app.db import connect

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path, readonly=True)
    try:
        claims = conn.execute(
            "SELECT * FROM claims WHERE review_status = 'approved' ORDER BY id"
        ).fetchall()
        claims_data = []
        source_ids: set[str] = set()
        for r in claims:
            claim = _claim_to_dict(conn, r, site_url)
            legal = documents_for_claim(conn, r["id"])
            if legal:
                claim["legal_documents"] = [
                    {
                        "id": ld["id"],
                        "body": ld["body"],
                        "case_or_document": ld["case_or_document"],
                        "document_type": ld["document_type"],
                        "date": ld["doc_date"],
                        "finding": ld["finding"],
                        "does_not_establish": ld["does_not_establish"],
                    }
                    for ld in legal
                ]
                for ld in legal:
                    if ld["source_id"]:
                        source_ids.add(ld["source_id"])
            claims_data.append(claim)
            source_ids.update(e["source_id"] for e in claim["evidence"])

        rels = conn.execute(
            """SELECT cr.*, o.name AS company_name FROM corporate_relationships cr
               JOIN organizations o ON o.id = cr.company_org_id
               WHERE cr.review_status = 'approved' ORDER BY cr.id"""
        ).fetchall()
        companies_data = []
        for r in rels:
            timeline = relationship_timeline(conn, r["company_org_id"])
            companies_data.append(
                {
                    "id": r["id"],
                    "company": r["company_name"],
                    "service": r["service"],
                    "customer": r["customer"],
                    "classification": r["classification"],
                    "start_date": r["start_date"],
                    "end_date": r["end_date"],
                    "confidence": r["confidence"],
                    "company_response": r["company_response"],
                    "evidence_ids": json.loads(r["evidence_ids_json"] or "[]"),
                    "last_reviewed": r["last_reviewed"],
                    "timeline": list(timeline),
                    "url": f"/company/{r['company_name'].lower().replace(' ', '-')}/",
                }
            )

        alts = conn.execute(
            "SELECT * FROM alternatives WHERE review_status = 'approved' ORDER BY category, id"
        ).fetchall()
        alternatives_data = []
        for a in alts:
            guide = migration_guide_fields(a)
            alternatives_data.append(
                {
                    "id": a["id"],
                    "product": a["product"],
                    "company": a["company"],
                    "category": a["category"],
                    "alternative": a["alternative"],
                    "alternative_license": a["alternative_license"],
                    "alternative_hosting": a["alternative_hosting"],
                    "self_hosting_available": bool(a["self_hosting_available"]),
                    "migration_difficulty": a["migration_difficulty"],
                    "privacy_notes": a["privacy_notes"],
                    "alternative_url": a["alternative_url"],
                    "score": alternative_score(a),
                    "score_dimensions": json.loads(a["score_json"] or "{}"),
                    "migration_guide": guide,
                }
            )

        # sources: referenced by evidence, legal docs, alternatives + all books
        for a in alts:
            source_ids.update(json.loads(a["source_ids_json"] or "[]"))
        for s in conn.execute("SELECT id FROM sources WHERE doc_kind = 'book'").fetchall():
            source_ids.add(s["id"])

        legal = conn.execute(
            "SELECT * FROM legal_documents WHERE review_status = 'approved'"
            " ORDER BY doc_date DESC, id"
        ).fetchall()
        legal_data = []
        for ld in legal:
            entry = document_summary(ld)
            entry["claims"] = [
                c["id"]
                for c in conn.execute(
                    """SELECT c.id FROM claim_legal_documents cld
                       JOIN claims c ON c.id = cld.claim_id
                       WHERE cld.legal_document_id = ? AND c.review_status = 'approved'""",
                    (ld["id"],),
                ).fetchall()
            ]
            legal_data.append(entry)
            if ld["source_id"]:
                source_ids.add(ld["source_id"])

        sources_data = [_source_to_dict(conn, sid) for sid in sorted(source_ids)]
        sources_data = [s for s in sources_data if s is not None]
    finally:
        conn.close()

    payloads: dict[str, list[Any]] = {
        "claims.json": claims_data,
        "sources.json": sources_data,
        "companies.json": companies_data,
        "alternatives.json": alternatives_data,
        "legal.json": legal_data,
    }
    counts: dict[str, int] = {}
    for name, data in payloads.items():
        (out / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        counts[name] = len(data)
    return counts


def export_site_data(
    db_path: str | Path, web_dir: str | Path, *, site_url: str = ""
) -> dict[str, int]:
    """Export site JSON (claims/sources/companies/alternatives/legal + stats)."""
    counts = export_all(db_path, Path(web_dir) / "data", site_url=site_url)
    from app.analytics import compute_stats
    from app.db import connect as db_connect

    conn = db_connect(db_path, readonly=True)
    try:
        stats = compute_stats(conn)
    finally:
        conn.close()
    data_dir = Path(web_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts["stats.json"] = 1
    return counts
