"""Runtime configuration loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    provider: str = "local"
    endpoint: str = "http://localhost:1234/v1"
    model: str = ""
    api_key: str = ""


@dataclass
class Config:
    db_path: Path
    site_url: str
    archive_dir: Path
    generated_dir: Path
    web_dir: Path
    llm: LLMConfig = field(default_factory=LLMConfig)

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env loader: KEY=VALUE lines, # comments, no interpolation."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values.setdefault(key.strip(), value.strip().strip("'\""))
    return values


def load_config(env_file: str | Path | None = None, repo_root: Path | None = None) -> Config:
    """Build Config from .env + environment. Environment variables win."""
    root = repo_root or Path(__file__).resolve().parent.parent
    env_values = _load_dotenv(Path(env_file) if env_file else root / ".env")

    def get(key: str, default: str) -> str:
        return os.environ.get(key) or env_values.get(key) or default

    db_path = Path(get("OE_DB_PATH", str(root / "data" / "evidence.db"))).resolve()
    return Config(
        db_path=db_path,
        site_url=get("OE_SITE_URL", "").rstrip("/"),
        archive_dir=Path(get("OE_ARCHIVE_DIR", str(root / "archive"))).resolve(),
        generated_dir=Path(get("OE_GENERATED_DIR", str(root / "data" / "generated"))).resolve(),
        web_dir=Path(get("OE_WEB_DIR", str(root / "web"))).resolve(),
        llm=LLMConfig(
            provider=get("OE_LLM_PROVIDER", "local"),
            endpoint=get("OE_LLM_ENDPOINT", "http://localhost:1234/v1"),
            model=get("OE_LLM_MODEL", ""),
            api_key=get("OE_LLM_API_KEY", ""),
        ),
    )
