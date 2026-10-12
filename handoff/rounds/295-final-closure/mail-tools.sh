#!/usr/bin/env bash
# One detached test-host batch. Each step keeps its own log/status; no early
# green shortcut. This script must be invoked via remote-check.sh run.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-295-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
FAILED=0
step() {
  local name=$1
  shift
  if [[ -n "${FINAL_BATCH_ONLY:-}" && ",$FINAL_BATCH_ONLY," != *",${name:0:2},"* ]]; then
    echo "BATCH-SKIP $name (explicit subset, unverified)"
    return
  fi
  echo "BATCH-START $name"
  "$@" >"$LOG_DIR/$name.log" 2>&1
  local code=$?
  printf '%s\n' "$code" >"$LOG_DIR/$name.status"
  printf 'BATCH-END %s exit=%s log=%s\n' "$name" "$code" "$LOG_DIR/$name.log"
  if (( code != 0 )); then FAILED=1; fi
}
step 06-mail-documents uv run python e2e/parity/parity.py --only=letters-confirm,letter-preview --wide --strict
step 06-approved-additions uv run python e2e/parity/parity.py --only=admin-article-revisions,admin-article-revision,admin-mail-samples,admin-mail-sample --wide --strict
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
