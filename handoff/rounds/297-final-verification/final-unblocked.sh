#!/usr/bin/env bash
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT"
LOG_DIR=${FINAL_BATCH_LOG_DIR:-/srv/sjtu-ow-check/final-297-last-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$LOG_DIR"
export TMPDIR=/srv/sjtu-ow-check/tmp/297-last
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
step 03-account-last-two uv run python e2e/parity/parity.py --account-errors --only=error-reset-expired,error-email-occupied --wide --strict
step 04-pages-webkit node scripts/journey.mjs pages --engine=webkit
step 05-priority-parity uv run python e2e/parity/parity.py --only=admin-home,admin-log,email-samples,admin-prerender-redirect --wide --strict
step 06-targeted-parity uv run python e2e/parity/parity.py --only=admin-article,admin-articles,admin-category,admin-collections,admin-font,admin-group,admin-image,admin-intro,admin-letters-confirm,admin-manual,admin-moderation,admin-page,admin-pins,admin-registration,admin-registrations,admin-roles,admin-scrim-announce,admin-scrims,admin-settings,admin-split-board,admin-team,admin-tournament-announce,admin-tournaments,admin-typography,admin-upload,admin-user --wide --strict
echo "BATCH-FINISHED failed=$FAILED log_dir=$LOG_DIR"
exit "$FAILED"
