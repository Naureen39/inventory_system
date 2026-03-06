#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="$BASE_DIR/inventory.db"
BACKUP_DIR="$BASE_DIR/backups"
STAMP="$(date +%F_%H-%M-%S)"
BACKUP_FILE="$BACKUP_DIR/inventory_${STAMP}.db"

mkdir -p "$BACKUP_DIR"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 command not found"
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database not found at $DB_PATH"
  exit 1
fi

sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
chmod 600 "$BACKUP_FILE"

# Keep the newest 30 backups, delete older ones.
ls -1t "$BACKUP_DIR"/inventory_*.db 2>/dev/null | tail -n +31 | xargs -r rm -f

echo "Backup created: $BACKUP_FILE"
