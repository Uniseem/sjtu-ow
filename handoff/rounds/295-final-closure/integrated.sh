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
step 01-full sh scripts/check.sh
step 06-remaining-pages uv run python e2e/parity/parity.py --only=admin,styleguide,email,unsubscribe,sitemap,robots,favicon,apple-touch-icon --wide --strict
step 06-components uv run python e2e/parity/parity.py --components --wide --strict
step 06-accounts uv run python e2e/parity/parity.py --accounts --wide --strict
step 06-account-errors uv run python e2e/parity/parity.py --account-errors --wide --strict
step 06-error-pages uv run python e2e/parity/error_pages.py
for engine in chromium webkit; do
  for mode in newbie admin pages; do
    step "07-journey-$engine-$mode" node scripts/journey.mjs "$mode" "--engine=$engine"
  done
done
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
