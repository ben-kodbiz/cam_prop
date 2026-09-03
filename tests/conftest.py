"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from app.db import connect, init_db


@pytest.fixture()
def tmp_db(tmp_path):
    """Fresh schema-only database per test."""
    path = tmp_path / "evidence.db"
    init_db(path)
    conn = connect(path)
    yield conn
    conn.close()
