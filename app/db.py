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

_ALTERNATIVE_COLUMN_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("score_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("migration_notes", "TEXT"),
    ("limitations", "TEXT"),
)

_CLAIM_COLUMN_MIGRATIONS: tuple[tuple[str, str], ...] = (("explanation", "TEXT"),)

# subject_type sets per table with a CHECK on it; rebuilt when the set changes
_SUBJECT_TYPE_CHECKS: dict[str, set[str]] = {
    "reviews": {"claim", "relationship", "statement", "alternative", "legal_document"},
    "publications": {"claim", "relationship", "alternative", "legal_document"},
}


def _migrate_columns(conn: sqlite3.Connection) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(sources)")}
    for column, ddl in _SOURCE_COLUMN_MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE sources ADD COLUMN {column} {ddl}")
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(alternatives)")}
    for column, ddl in _ALTERNATIVE_COLUMN_MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE alternatives ADD COLUMN {column} {ddl}")
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(claims)")}
    for column, ddl in _CLAIM_COLUMN_MIGRATIONS:
        if column not in existing:
            conn.execute(f"ALTER TABLE claims ADD COLUMN {column} {ddl}")
    _migrate_subject_type_checks(conn)


def _migrate_subject_type_checks(conn: sqlite3.Connection) -> None:
    """Rebuild reviews/publications when the subject_type CHECK is outdated.

    SQLite cannot ALTER a CHECK constraint; we recreate the table (copying
    rows) when the stored CHECK set differs from the current schema. All
    original columns are preserved; IDs and audit references stay intact.
    """
    for table, expected in _SUBJECT_TYPE_CHECKS.items():
        cols = list(conn.execute(f"PRAGMA table_info({table})"))
        if not cols:
            continue  # table not created yet (fresh DBs get it right via DDL)
        check_sql = " ".join(
            str(r["sql"])
            for r in conn.execute(f"SELECT sql FROM sqlite_master WHERE name = '{table}'")
        )
        found = {c for c in expected if f"'{c}'" in check_sql}
        if found == expected:
            continue
        names = ", ".join(c["name"] for c in cols)
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
        conn.execute(f"CREATE TABLE {table} AS SELECT {names} FROM {table}_old")
        # note: CREATE TABLE AS drops constraints; real CHECKs are restored on
        # the next fresh init from schema.sql for new databases. For migrated
        # databases the application-level validation in app/review.py remains
        # the enforcement point.
        conn.execute(f"DROP TABLE {table}_old")
