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
                "source_tier": e["source_tier"],
                "published_at": e["published_at"],
                "strength": e["strength"],
            }
            for e in ev
        ],
        "search_text": normalize_claim_text(row["claim_text"]),
    }


def export_all(db_path: str | Path, out_dir: str | Path, *, site_url: str = "") -> dict[str, int]:
    """Write data/claims.json, companies.json, sources.json, alternatives.json.

    Returns counts. Only approved claims / relationships / alternatives are
    included; sources referenced by exported evidence are included.
    """
    from app.db import connect

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path, readonly=True)
    try:
        claims = conn.execute(
            "SELECT * FROM claims WHERE review_status = 'approved' ORDER BY id"
        ).fetchall()
        claims_data = [_claim_to_dict(conn, r, site_url) for r in claims]

        source_ids: set[str] = set()
        for c in claims_data:
            source_ids.update(e["source_id"] for e in c["evidence"])
        sources_data = []
        for sid in sorted(source_ids):
            s = conn.execute("SELECT * FROM sources WHERE id = ?", (sid,)).fetchone()
            if s:
                sources_data.append(
                    {
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
                    }
                )

        rels = conn.execute(
            """SELECT cr.*, o.name AS company_name FROM corporate_relationships cr
               JOIN organizations o ON o.id = cr.company_org_id
               WHERE cr.review_status = 'approved' ORDER BY cr.id"""
        ).fetchall()
        companies_data = []
        for r in rels:
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
                    "url": f"/company/{r['company_name'].lower().replace(' ', '-')}/",
                }
            )

        alts = conn.execute(
            "SELECT * FROM alternatives WHERE review_status = 'approved' ORDER BY category, id"
        ).fetchall()
        alternatives_data = [
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
            }
            for a in alts
        ]
    finally:
        conn.close()

    payloads = {
        "claims.json": claims_data,
        "sources.json": sources_data,
        "companies.json": companies_data,
        "alternatives.json": alternatives_data,
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
    """Export straight into web/data/ for static deployment."""
    return export_all(db_path, Path(web_dir) / "data", site_url=site_url)
