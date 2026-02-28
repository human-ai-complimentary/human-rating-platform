#!/usr/bin/env bash
set -euo pipefail

# Resolve Render deploy target from:
# - Manual override (workflow_dispatch input)
# - Changed file paths between base/head commits
#
# Expected env (all optional):
#   EVENT_NAME            GitHub event name (e.g. push, workflow_dispatch)
#   MANUAL_TARGET         auto | api | web | both
#   GITHUB_SHA            SHA associated with this workflow run
#   GITHUB_EVENT_BEFORE   github.event.before SHA for push events
#   GITHUB_OUTPUT         GitHub Actions output file path
#
# Emits:
#   target         none | api | web | both
#   reason         explanation string
#   changed_count  number of changed files (or 'manual' / 'unknown')
#   changed_files  comma-separated preview (max 20) or 'manual override' / 'fail-open'

ZERO_SHA="0000000000000000000000000000000000000000"

EVENT_NAME="${EVENT_NAME:-}"
MANUAL_TARGET="${MANUAL_TARGET:-auto}"
GITHUB_SHA="${GITHUB_SHA:-}"
GITHUB_EVENT_BEFORE="${GITHUB_EVENT_BEFORE:-}"
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

emit_result() {
  local target="$1"
  local reason="$2"
  local changed_count="$3"
  local changed_files="$4"

  emit_output "target" "$target"
  emit_output "reason" "$reason"
  emit_output "changed_count" "$changed_count"
  emit_output "changed_files" "$changed_files"
}

commit_exists() {
  local sha="$1"
  [ -n "$sha" ] || return 1
  git cat-file -e "${sha}^{commit}" >/dev/null 2>&1
}

append_reason_note() {
  local note="$1"
  [ -n "$note" ] || return 0
  if [ -n "${reason_notes:-}" ]; then
    reason_notes="${reason_notes}; ${note}"
  else
    reason_notes="$note"
  fi
}

with_reason_notes() {
  local base_reason="$1"
  if [ -n "${reason_notes:-}" ]; then
    printf '%s | notes: %s' "$base_reason" "$reason_notes"
  else
    printf '%s' "$base_reason"
  fi
}

resolve_default_branch_ref() {
  git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || true
}

try_diff() {
  local base_sha="$1"
  local head_sha="$2"
  local attempt_label="$3"

  [ -n "$base_sha" ] || return 1
  if ! commit_exists "$base_sha"; then
    append_reason_note "${attempt_label}: base missing (${base_sha:0:7})"
    return 1
  fi

  if diff_output="$(git diff --name-only "$base_sha" "$head_sha" 2>&1)"; then
    changed_files="$diff_output"
    reason="$(with_reason_notes "auto path routing (${attempt_label} ${base_sha:0:7}..${head_sha:0:7})")"
    return 0
  fi

  append_reason_note "${attempt_label}: diff failed (${base_sha:0:7}..${head_sha:0:7})"
  return 1
}

if [ "$EVENT_NAME" = "workflow_dispatch" ] && [ "$MANUAL_TARGET" != "auto" ]; then
  case "$MANUAL_TARGET" in
    api|web|both)
      emit_result "$MANUAL_TARGET" "manual override" "manual" "manual override"
      exit 0
      ;;
    *)
      echo "error: invalid manual target: $MANUAL_TARGET" >&2
      exit 1
      ;;
  esac
fi

reason_notes=""
changed_files=""
reason=""

if [ -n "$GITHUB_SHA" ] && commit_exists "$GITHUB_SHA"; then
  head_sha="$GITHUB_SHA"
else
  head_sha="$(git rev-parse HEAD)"
  if [ -n "$GITHUB_SHA" ] && [ "$GITHUB_SHA" != "$head_sha" ]; then
    append_reason_note "provided GITHUB_SHA unavailable (${GITHUB_SHA:0:7}); used HEAD"
  fi
fi

if ! commit_exists "$head_sha"; then
  emit_result "both" "fail-open: head commit unavailable (${head_sha:0:7})" "unknown" "fail-open"
  exit 0
fi

if [ "$EVENT_NAME" = "push" ] && [ -n "$GITHUB_EVENT_BEFORE" ] && [ "$GITHUB_EVENT_BEFORE" != "$ZERO_SHA" ]; then
  try_diff "$GITHUB_EVENT_BEFORE" "$head_sha" "push diff" || true
elif [ "$EVENT_NAME" = "push" ] && [ "$GITHUB_EVENT_BEFORE" = "$ZERO_SHA" ]; then
  append_reason_note "push before was zero SHA (new branch or rewritten history)"
fi

if [ -z "$reason" ] && parent_sha="$(git rev-parse "${head_sha}^" 2>/dev/null)"; then
  try_diff "$parent_sha" "$head_sha" "head parent diff" || true
fi

if [ -z "$reason" ]; then
  default_branch_ref="$(resolve_default_branch_ref)"
  if [ -n "$default_branch_ref" ]; then
    merge_base="$(git merge-base "$head_sha" "$default_branch_ref" 2>/dev/null || true)"
    if [ -n "$merge_base" ]; then
      try_diff "$merge_base" "$head_sha" "merge-base diff (${default_branch_ref})" || true
    else
      append_reason_note "merge-base unavailable against ${default_branch_ref}"
    fi
  else
    append_reason_note "default branch reference unavailable"
  fi
fi

if [ -z "$reason" ]; then
  if changed_files="$(git ls-tree -r --name-only "$head_sha" 2>/dev/null)"; then
    reason="$(with_reason_notes "auto path routing (snapshot fallback ${head_sha:0:7})")"
  else
    emit_result "both" "$(with_reason_notes "fail-open: unable to compute changed files for ${head_sha:0:7}")" "unknown" "fail-open"
    exit 0
  fi
fi

deploy_api=false
deploy_web=false

while IFS= read -r file; do
  [ -n "$file" ] || continue

  case "$file" in
    backend/*)
      deploy_api=true
      ;;
    frontend/*)
      deploy_web=true
      ;;
    scripts/deploy.sh|scripts/resolve_deploy_target.sh|scripts/resolve_deploy_commit_sha.sh|.github/workflows/deploy.yml)
      deploy_api=true
      deploy_web=true
      ;;
  esac
done <<< "$changed_files"

target="none"
if [ "$deploy_api" = true ] && [ "$deploy_web" = true ]; then
  target="both"
elif [ "$deploy_api" = true ]; then
  target="api"
elif [ "$deploy_web" = true ]; then
  target="web"
fi

changed_count="$(printf '%s\n' "$changed_files" | sed '/^$/d' | wc -l | tr -d ' ')"
changed_preview="$(printf '%s\n' "$changed_files" | sed '/^$/d' | head -n 20 | paste -sd ',' -)"
if [ -z "$changed_preview" ]; then
  changed_preview="(none)"
fi

emit_result "$target" "$reason" "$changed_count" "$changed_preview"
