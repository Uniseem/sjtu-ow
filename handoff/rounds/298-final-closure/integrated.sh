#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-298-integrated-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/298-integrated
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
step 01-full sh scripts/check.sh
step 02-account-navigation uv run python e2e/parity/parity.py --account-errors --only=error-reset-expired,error-email-occupied,error-email-expired,error-email-third-attempt,error-signup-existing --wide --strict
step 03-parity uv run python e2e/parity/parity.py --wide --strict
step 04-admin-chromium node scripts/journey.mjs admin --engine=chromium
step 05-admin-webkit node scripts/journey.mjs admin --engine=webkit
step 06-pages-webkit node scripts/journey.mjs pages --engine=webkit
step 07-caddy bash e2e/caddy/smoke.sh
step 08-admin-browser bash -c 'cd web/apps/admin && node browser-check.mjs /usr/bin/chromium'
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
