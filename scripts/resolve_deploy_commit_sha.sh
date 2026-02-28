#!/usr/bin/env bash
set -euo pipefail

# Resolve the commit SHA that Render should deploy.
#
# Expected env (all optional):
#   REQUESTED_COMMIT_SHA   Manual workflow input commit SHA override
#   GITHUB_SHA             Workflow commit SHA fallback
#   GITHUB_OUTPUT          GitHub Actions output file path
#
# Emits:
#   target_sha             Resolved 40-char SHA
#   target_reason          workflow SHA | manual commit_sha input

REQUESTED_COMMIT_SHA="${REQUESTED_COMMIT_SHA:-}"
GITHUB_SHA="${GITHUB_SHA:-}"
OUTPUT_FILE="${GITHUB_OUTPUT:-}"

emit_output() {
  local key="$1"
  local value="$2"

  if [ -n "$OUTPUT_FILE" ]; then
    printf '%s=%s\n' "$key" "$value" >> "$OUTPUT_FILE"
  else
    printf '%s=%s\n' "$key" "$value"
  fi
}

commit_exists() {
  local sha="$1"
  [ -n "$sha" ] || return 1
  git cat-file -e "${sha}^{commit}" >/dev/null 2>&1
}

requested="$(printf '%s' "$REQUESTED_COMMIT_SHA" | tr '[:upper:]' '[:lower:]' | xargs)"

if [ -z "$requested" ]; then
  target_sha="$GITHUB_SHA"
  target_reason="workflow SHA"
  if [ -z "$target_sha" ]; then
    echo "error: GITHUB_SHA is not set and no commit_sha override was provided" >&2
    exit 1
  fi
else
  if [[ ! "$requested" =~ ^[0-9a-f]{40}$ ]]; then
    echo "error: commit_sha must be a 40-character hexadecimal SHA" >&2
    exit 1
  fi

  if ! commit_exists "$requested"; then
    git fetch --no-tags origin "$requested" || true
  fi
  if ! commit_exists "$requested"; then
    echo "error: commit_sha ${requested} is not reachable in this repository context" >&2
    exit 1
  fi

  target_sha="$requested"
  target_reason="manual commit_sha input"
fi

if ! commit_exists "$target_sha"; then
  echo "error: resolved deploy SHA ${target_sha} is not available in this checkout" >&2
  exit 1
fi

emit_output "target_sha" "$target_sha"
emit_output "target_reason" "$target_reason"
