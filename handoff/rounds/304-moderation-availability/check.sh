#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
if [ "${1:-all}" = web ]; then
  (cd web; pnpm install --frozen-lockfile; pnpm test)
else
  sh scripts/check.sh
fi
export UI_OUTPUT="$(cd .. && pwd)/304-ui"
node handoff/rounds/302-admin-visual-cleanup/browser.mjs
git diff --check origin/main HEAD
