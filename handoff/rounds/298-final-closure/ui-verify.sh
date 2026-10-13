#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-298-ui-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/298-ui
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
step 00-prepare bash handoff/rounds/298-final-closure/prepare.sh
step 01-accounts bash -c 'cd server && go test ./internal/accounts -run TestReauthenticateAndEmailChange -count=1'
step 02-build bash -c 'cd web && pnpm --filter @sjtu-ow/admin build'
step 03-admin-parity uv run python e2e/parity/parity.py --only=admin --wide --strict
step 04-account-occupied uv run python e2e/parity/parity.py --account-errors --only=error-email-occupied --wide --strict
step 05-admin-chromium node scripts/journey.mjs admin --engine=chromium
step 06-admin-webkit node scripts/journey.mjs admin --engine=webkit
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
