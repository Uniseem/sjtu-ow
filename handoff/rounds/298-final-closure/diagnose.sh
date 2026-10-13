#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-298-diagnose-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/298
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
step 00-build bash -c 'cd web && pnpm install --frozen-lockfile && pnpm --filter @sjtu-ow/site build && pnpm --filter @sjtu-ow/admin build'
step 01-components uv run python e2e/parity/parity.py --components --wide --strict
step 02-account-last-two uv run python e2e/parity/parity.py --account-errors --only=error-reset-expired,error-email-occupied --wide --strict
step 03-admin-parity uv run python e2e/parity/parity.py --only=admin,email-samples --wide --strict
step 04-caddy bash e2e/caddy/smoke.sh
step 05-admin-browser bash -c 'cd web/apps/admin && node browser-check.mjs /usr/bin/chromium'
step 06-admin-chromium node scripts/journey.mjs admin --engine=chromium
step 07-admin-webkit node scripts/journey.mjs admin --engine=webkit
step 08-pages-webkit node scripts/journey.mjs pages --engine=webkit
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
