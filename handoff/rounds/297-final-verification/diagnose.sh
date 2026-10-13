#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-297-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/297
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
step 01-full sh scripts/check.sh
step 02-components uv run python e2e/parity/parity.py --components --wide --strict
step 03-account-state-errors uv run python e2e/parity/parity.py --account-errors --only=error-email-expired,error-email-third-attempt,error-reset-expired,error-signup-existing,error-email-occupied --wide --strict
step 04-error-pages uv run python e2e/parity/error_pages.py
for engine in chromium webkit; do
  for mode in newbie admin pages; do
    step "05-journey-$engine-$mode" node scripts/journey.mjs "$mode" "--engine=$engine"
  done
done
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
