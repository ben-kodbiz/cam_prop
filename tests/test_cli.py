"""CLI smoke tests."""

from __future__ import annotations

import json

from app.cli import main


def test_cli_full_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OE_DB_PATH", str(tmp_path / "data" / "evidence.db"))
    monkeypatch.setenv("OE_GENERATED_DIR", str(tmp_path / "data" / "generated"))
    monkeypatch.setenv("OE_WEB_DIR", str(tmp_path / "web"))
    monkeypatch.setenv("OE_ARCHIVE_DIR", str(tmp_path / "archive"))
    monkeypatch.setenv("OE_SITE_URL", "https://example.org")

    from app.config import load_config

    cfg = load_config()
    assert cfg.db_path == tmp_path / "data" / "evidence.db"
    # schema file must exist relative to repo, not cwd
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / "data" / "schema.sql").is_file()

    assert main(["init-db"]) == 0
    assert (tmp_path / "data" / "evidence.db").is_file()

    assert main(["seed"]) == 0
    assert main(["export"]) == 0
    out_dir = tmp_path / "data" / "generated"
    assert (out_dir / "claims.json").is_file()
    data = json.loads((out_dir / "claims.json").read_text())
    assert len(data) == 1
    assert main(["queue"]) == 0
    assert main(["stats"]) == 0
    assert main(["search", "seed"]) == 0


def test_cli_backup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OE_DB_PATH", str(tmp_path / "data" / "evidence.db"))
    assert main(["init-db"]) == 0
    assert main(["backup", "--out", str(tmp_path / "b.db")]) == 0
    assert (tmp_path / "b.db").is_file()
