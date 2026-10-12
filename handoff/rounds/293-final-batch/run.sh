#!/usr/bin/env bash
# One detached test-host batch. Each step keeps its own log/status; no early
# green shortcut. This script must be invoked via remote-check.sh run.
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-293-$(date +%Y%m%d-%H%M%S)}
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
step 01-full sh scripts/check.sh
step 02-mutations-290 uv run python handoff/rounds/290-f6-f9-full-frontend/mutate.py
step 02-mutations-293 uv run python handoff/rounds/293-final-batch/mutate.py
step 02-input-guards python3 -m unittest discover -s deploy -p test_rehearsal_input.py
step 03-site-browser bash -c 'cd web/apps/site && node browser-check.mjs /usr/bin/chromium'
step 03-admin-browser bash -c 'cd web/apps/admin && node browser-check.mjs /usr/bin/chromium'
step 03-comments-browser bash -c 'cd web/apps/site && node comments-browser-check.mjs /usr/bin/chromium'
step 04-real-accounts uv run python handoff/rounds/284-f3-real-accounts/run_real_accounts.py
step 04-real-comments uv run python handoff/rounds/283-f4-real-comments/run_real_comments.py
step 04-api-build bash -c 'cd server && go build -o /tmp/sjtuow-293 ./cmd/sjtuow'
step 04-api uv run python handoff/rounds/290-f6-f9-full-frontend/api-journey.py --binary /tmp/sjtuow-293 --repo "$ROOT"
step 04-personal uv run python handoff/rounds/290-f6-f9-full-frontend/run_real_personal.py
step 05-caddy bash e2e/caddy/smoke.sh
step 06-parity bash e2e/parity/run.sh --wide --strict
step 06-components bash e2e/parity/run.sh --components --wide --strict
step 06-accounts bash e2e/parity/run.sh --accounts --wide --strict
step 06-account-errors bash e2e/parity/run.sh --account-errors --wide --strict
step 06-error-pages uv run python e2e/parity/error_pages.py
for engine in chromium webkit; do
  for mode in newbie admin pages; do
    step "07-journey-$engine-$mode" node scripts/journey.mjs "$mode" "--engine=$engine"
  done
done
step 09-budget bash -c 'cd web/apps/site && node budget.mjs'
# Actual production backup runs are performed separately over the explicitly
# authorized stream, twice with latest backups. Never put their content here.
step 11-final-full sh scripts/check.sh
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
