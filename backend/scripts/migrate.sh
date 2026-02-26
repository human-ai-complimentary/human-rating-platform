#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BACKEND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$BACKEND_DIR"

export PATH="$HOME/.local/bin:$PATH"
# Thin wrapper to keep Alembic invocation consistent across local/dev/CI/Render.
# Usage examples:
#   sh scripts/migrate.sh upgrade head
#   sh scripts/migrate.sh downgrade -1
#   sh scripts/migrate.sh revision --autogenerate --rev-id "$(date -u +%Y%m%d%H%M%S)" -m "add_index"
exec uv run --no-sync alembic -c alembic.ini "$@"
