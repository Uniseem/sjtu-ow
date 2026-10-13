#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-298-checks-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/298-final
export GOTMPDIR=$TMPDIR/go
mkdir -p "$GOTMPDIR"
FAILED=0
step() {
  local name=$1; shift
  echo "BATCH-START $name"
  "$@" >"$LOG_DIR/$name.log" 2>&1
  local code=$?
  printf '%s\n' "$code" >"$LOG_DIR/$name.status"
  printf 'BATCH-END %s exit=%s log=%s\n' "$name" "$code" "$LOG_DIR/$name.log"
  if (( code != 0 )); then FAILED=1; fi
}
step 01-full sh scripts/check.sh
step 02-mutations uv run python handoff/rounds/298-final-closure/mutate.py
step 03-content-mutations uv run python handoff/rounds/298-final-closure/mutate-content.py
step 04-caddy bash e2e/caddy/smoke.sh
step 05-admin-browser bash -c 'cd web/apps/admin && node browser-check.mjs /usr/bin/chromium'
step 06-real-accounts uv run python handoff/rounds/284-f3-real-accounts/run_real_accounts.py
step 07-admin-chromium node scripts/journey.mjs admin --engine=chromium
step 08-admin-webkit node scripts/journey.mjs admin --engine=webkit
step 09-pages-webkit node scripts/journey.mjs pages --engine=webkit
step 10-real-rehearsal bash handoff/rounds/293-final-batch/real-rehearsal.sh
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
