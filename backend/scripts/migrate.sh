#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$BACKEND_DIR"

# Thin wrapper only: pass through to Alembic with repo-local config.
exec uv run --no-sync alembic -c alembic.ini "$@"
