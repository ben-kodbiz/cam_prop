"""Allow running as `python -m app`."""

from __future__ import annotations

from app.cli import main

raise SystemExit(main())
