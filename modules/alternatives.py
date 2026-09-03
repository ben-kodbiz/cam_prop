"""Alternatives module (agentodo §14-16).

Documents real, maintained open-source alternatives. Never claims any
option is "100% ethical" — states what it provides instead.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app import audit
from app.util import next_id, utcnow_iso


class AlternativeError(ValueError):
    pass


CATEGORIES = (
    "cloud_storage",
    "office_suites",
    "email",
    "search",
    "cloud_computing",
    "kubernetes_hosting",
    "ci_cd",
    "git_hosting",
    "video_conferencing",
    "analytics",
    "dns",
    "monitoring",
    "object_storage",
    "databases",
    "ai_inference",
    "ai_development",
    "password_management",
)


def create_alternative(
    conn: sqlite3.Connection,
    *,
    product: str,
    alternative: str,
    category: str,
    company: str | None = None,
    alternative_license: str | None = None,
    alternative_hosting: str | None = None,
    self_hosting_available: bool | None = None,
    migration_difficulty: str | None = None,
    privacy_notes: str | None = None,
    replaces_url: str | None = None,
    alternative_url: str | None = None,
    source_ids: list[str] | None = None,
    score: dict[str, float] | None = None,
    migration_notes: str | None = None,
    limitations: str | None = None,
    notes: str | None = None,
    actor: str = "system",
    alternative_id: str | None = None,
) -> str:
    if category not in CATEGORIES:
        msg = f"unknown category {category!r}; known: {CATEGORIES}"
        raise AlternativeError(msg)
    if migration_difficulty is not None and migration_difficulty not in (
        "easy",
        "moderate",
        "hard",
    ):
        msg = f"migration_difficulty must be easy|moderate|hard, got {migration_difficulty!r}"
        raise AlternativeError(msg)
    dims = _validate_score(score or {})
    for sid in source_ids or []:
        if not conn.execute("SELECT 1 FROM sources WHERE id = ?", (sid,)).fetchone():
            msg = f"source {sid} does not exist"
            raise AlternativeError(msg)
    now = utcnow_iso()
    aid = alternative_id or next_id(conn, "alternatives", "ALT")
    conn.execute(
        """INSERT INTO alternatives (id, product, company, category, alternative,
             alternative_license, alternative_hosting, self_hosting_available,
             migration_difficulty, privacy_notes, replaces_url, alternative_url,
             source_ids_json, score_json, migration_notes, limitations, notes,
             review_status, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   'pending', 1, ?, ?)""",
        (
            aid,
            product,
            company,
            category,
            alternative,
            alternative_license,
            alternative_hosting,
            1 if self_hosting_available else (0 if self_hosting_available is not None else None),
            migration_difficulty,
            privacy_notes,
            replaces_url,
            alternative_url,
            json.dumps(source_ids or []),
            json.dumps(dims, ensure_ascii=False, sort_keys=True),
            migration_notes,
            limitations,
            notes,
            now,
            now,
        ),
    )
    audit.log(
        conn,
        actor,
        "create",
        "alternative",
        aid,
        {"product": product, "alternative": alternative, "category": category},
    )
    return aid


# Practical dimensions from agentodo §45. Never political affiliation.
ALTERNATIVE_SCORE_DIMENSIONS: tuple[str, ...] = (
    "open_source",
    "self_hostable",
    "active_development",
    "security",
    "documentation",
    "migration",
    "cost",
    "lock_in",
    "privacy",
    "community",
)


def _validate_score(score: dict[str, float]) -> dict[str, float]:
    dims = {k: float(v) for k, v in score.items() if k in ALTERNATIVE_SCORE_DIMENSIONS}
    for k, v in dims.items():
        if not 0 <= v <= 5:
            msg = f"score dimension {k} must be 0-5, got {v}"
            raise AlternativeError(msg)
    return dims


def alternative_score(row: sqlite3.Row) -> float:
    """Overall practicality score 0-5 from the §45 dimensions (simple mean)."""
    dims = json.loads(row["score_json"] or "{}")
    if not dims:
        return 0.0
    return round(sum(float(v) for v in dims.values()) / len(dims), 2)


def iter_alternatives(
    conn: sqlite3.Connection,
    *,
    approved_only: bool = False,
) -> list[sqlite3.Row]:
    q = "SELECT * FROM alternatives"
    if approved_only:
        q += " WHERE review_status = 'approved'"
    q += " ORDER BY category, alternative"
    return conn.execute(q).fetchall()


def dependency_map(
    conn: sqlite3.Connection,
    *,
    approved_only: bool = True,
) -> list[dict[str, object]]:
    """Vendor-dependency mapping (§6): product -> available alternatives."""
    rows = iter_alternatives(conn, approved_only=approved_only)
    by_product: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = by_product.setdefault(
            row["product"],
            {
                "product": row["product"],
                "company": row["company"],
                "category": row["category"],
                "alternatives": [],
            },
        )
        entry["alternatives"].append(
            {
                "id": row["id"],
                "alternative": row["alternative"],
                "license": row["alternative_license"],
                "self_hosting": bool(row["self_hosting_available"]),
                "migration_difficulty": row["migration_difficulty"],
                "score": alternative_score(row),
                "url": row["alternative_url"],
            }
        )
    return list(by_product.values())


def migration_guide_fields(row: sqlite3.Row) -> dict[str, Any]:
    """Structured fields for user migration guides (§16)."""
    return {
        "replaces": row["product"],
        "why_choose": row["notes"] or "",
        "installation_difficulty": row["migration_difficulty"],
        "self_hosting": bool(row["self_hosting_available"]),
        "data_migration": row["migration_notes"] or row["migration_difficulty"],
        "limitations": row["limitations"] or "",
        "security_considerations": row["privacy_notes"] or "",
        "license": row["alternative_license"],
        "project_health": json.loads(row["score_json"] or "{}").get("active_development"),
        "score": alternative_score(row),
        "url": row["alternative_url"],
        "sources": json.loads(row["source_ids_json"] or "[]"),
    }
