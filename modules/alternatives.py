"""Alternatives module (agentodo §14-16).

Documents real, maintained open-source alternatives. Never claims any
option is "100% ethical" — states what it provides instead.
"""

from __future__ import annotations

import json
import sqlite3

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
             source_ids_json, notes, review_status, revision, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)""",
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


def iter_alternatives(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM alternatives ORDER BY category, alternative").fetchall()


def migration_guide_fields(row: sqlite3.Row) -> dict:
    """Structured fields for user migration guides (§16)."""
    return {
        "replaces": row["product"],
        "why_choose": row["notes"] or "",
        "installation_difficulty": row["migration_difficulty"],
        "self_hosting": bool(row["self_hosting_available"]),
        "data_migration": row["migration_difficulty"],
        "limitations": "",
        "security_considerations": row["privacy_notes"] or "",
        "license": row["alternative_license"],
        "project_health": "",
        "url": row["alternative_url"],
        "sources": json.loads(row["source_ids_json"] or "[]"),
    }
