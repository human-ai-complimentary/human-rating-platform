#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$BACKEND_DIR"

export PATH="$HOME/.local/bin:$PATH"

# ── 1. Config check ──────────────────────────────────────────────────────────
echo "🔍 Running pre-deploy config check..."
uv run --no-sync python scripts/config_check.py --target render

# ── 2. Database migrations ────────────────────────────────────────────────────
echo "🔄 Running database migrations..."
uv run --no-sync alembic -c alembic.ini upgrade head
