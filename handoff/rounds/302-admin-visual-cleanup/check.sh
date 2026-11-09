#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
export UI_OUTPUT=${UI_OUTPUT:-$(cd .. && pwd)/302-ui}
case "${1:-all}" in
  all) sh scripts/check.sh ;;
  web) (cd web; pnpm install --frozen-lockfile; pnpm test) ;;
  browser) ;;
  *) exit 2 ;;
esac
(
  cd web/apps/admin
  node browser-check.mjs /usr/bin/chromium
)
(
  cd web/apps/site
  node browser-check.mjs /usr/bin/chromium
)
node handoff/rounds/302-admin-visual-cleanup/browser.mjs
git diff --check origin/main HEAD
