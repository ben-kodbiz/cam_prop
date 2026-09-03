#!/usr/bin/env bash
# Backup SQLite DB, source metadata, claim JSON, config and hash manifests.
# Usage: scripts/backup.sh [destination_dir]  (default: scripts/backups/<timestamp>)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:-$ROOT/scripts/backups/$(date -u +%Y%m%dT%H%M%SZ)}"
DB="${OE_DB_PATH:-$ROOT/data/evidence.db}"

mkdir -p "$DEST"

if [ -f "$DB" ]; then
  # consistent snapshot via sqlite3 backup API (falls back to file copy)
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB" ".backup '$DEST/evidence.db'"
  else
    python3 - "$DB" "$DEST/evidence.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()
src.close()
PY
  fi
  echo "database -> $DEST/evidence.db"
else
  echo "warning: database not found at $DB" >&2
fi

for dir in "data/generated" "archive" "data/seed"; do
  if [ -d "$ROOT/$dir" ] && [ -n "$(ls -A "$ROOT/$dir" 2>/dev/null)" ]; then
    mkdir -p "$DEST/$(dirname "$dir")"
    cp -r "$ROOT/$dir" "$DEST/$dir"
    echo "$dir -> $DEST/$dir"
  fi
done

for f in .env pyproject.toml data/schema.sql; do
  if [ -f "$ROOT/$f" ]; then
    mkdir -p "$DEST/$(dirname "$f")"
    cp "$ROOT/$f" "$DEST/$f"
    echo "$f -> $DEST/$f"
  fi
done

# hash manifest for verification
find "$DEST" -type f ! -name sha256-manifest.txt -print0 \
  | sort -z | xargs -0 sha256sum > "$DEST/sha256-manifest.txt" || true
echo "manifest -> $DEST/sha256-manifest.txt"
echo "backup complete: $DEST"
