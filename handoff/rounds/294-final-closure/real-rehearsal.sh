#!/usr/bin/env bash
# Execute only on the test host after the explicitly authorized production
# backup has been streamed into this dedicated700 directory.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PRIVATE=/srv/sjtu-ow-rehearsal
test -f "$PRIVATE/input.tar.gz"
test "$(stat -c %a "$PRIVATE")" = 700
test "$(stat -c %a "$PRIVATE/input.tar.gz")" = 600
cleanup() {
  # Retire the dedicated directory before deleting, never delete a live DB.
  local retired="$PRIVATE-retired-$(date +%s)"
  mv "$PRIVATE" "$retired"
  rm -rf -- "$retired"
  test ! -e "$PRIVATE" && test ! -e "$retired"
  echo "REAL-REHEARSAL-DATA-REMOVED utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
trap cleanup EXIT
cd "$ROOT"
REHEARSAL_BROWSER_CHECK=1 bash deploy/rehearse.sh "$PRIVATE/input.tar.gz"
