#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-297-unblocked-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/297-unblocked
export GOTMPDIR=$TMPDIR/go
export PARITY_WORK=$TMPDIR/parity
mkdir -p "$GOTMPDIR"
FAILED=0
step() {
  local name=$1
  shift
  echo "BATCH-START $name"
  "$@" >"$LOG_DIR/$name.log" 2>&1
  local code=$?
  printf '%s\n' "$code" >"$LOG_DIR/$name.status"
  printf 'BATCH-END %s exit=%s log=%s\n' "$name" "$code" "$LOG_DIR/$name.log"
  if (( code != 0 )); then FAILED=1; fi
}
step 00-prepare bash handoff/rounds/295-final-closure/prepare.sh
step 01-full sh scripts/check.sh
step 02-components uv run python e2e/parity/parity.py --components --wide --strict
step 03-account-final-three uv run python e2e/parity/parity.py --account-errors --only=error-email-expired,error-reset-expired,error-email-occupied --wide --strict
step 04-pages-chromium node scripts/journey.mjs pages --engine=chromium
step 05-pages-webkit node scripts/journey.mjs pages --engine=webkit
step 06-priority-parity uv run python e2e/parity/parity.py --only=admin-home,admin-log,email-samples,admin-prerender-redirect --wide --strict
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
