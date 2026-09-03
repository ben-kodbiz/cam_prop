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
    """Create all tables/indexes from data/schema.sql (idempotent).

    Also applies lightweight column migrations for databases created
    before a column was added (CREATE TABLE IF NOT EXISTS alone cannot
    extend an existing table).
    """
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = connect(db_path)
    try:
        conn.executescript(schema)
        _migrate_columns(conn)
        conn.commit()
    finally:
        conn.close()


# column, definition — appended to `sources` when missing (lightweight migration)
_SOURCE_COLUMN_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("local_path", "TEXT"),
    ("doc_kind", "TEXT CHECK (doc_kind IN ('url', 'book'))"),
    ("book_author", "TEXT"),
    ("book_isbn", "TEXT"),
    ("book_publisher", "TEXT"),
    ("book_year", "TEXT"),
    ("book_pages", "INTEGER"),
)


def _migrate_columns(conn: sqlite3.Connection) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(sources)")}
    for column, ddl in _SOURCE_COLUMN_MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE sources ADD COLUMN {column} {ddl}")
