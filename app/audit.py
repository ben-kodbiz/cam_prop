"""Append-only audit log. Never silently rewrite history."""

from __future__ import annotations

import json
import sqlite3

from app.util import utcnow_iso


def log(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, object] | None = None,
    reason: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, actor, action, entity_type, entity_id, details_json, reason)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            utcnow_iso(),
            actor,
            action,
            entity_type,
            entity_id,
            json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            reason,
        ),
    )
