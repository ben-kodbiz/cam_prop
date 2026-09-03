"""SQLite connection management and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "schema.sql"


def connect(db_path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    """Open a connection with foreign keys and WAL enabled."""
    path = Path(db_path)
    if not readonly:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        f"file:{path}{'?mode=ro' if readonly else ''}",
        uri=True,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str | Path) -> None:
    """Create all tables/indexes from data/schema.sql (idempotent)."""
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
