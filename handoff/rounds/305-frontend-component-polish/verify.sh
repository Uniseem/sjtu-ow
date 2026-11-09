#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
sh scripts/check.sh
(
  cd web/apps/site
  node browser-check.mjs /usr/bin/chromium
)
(
  cd web/apps/admin
  node browser-check.mjs /usr/bin/chromium
)
UI_PROBE_ONLY=1 uv run python handoff/rounds/305-frontend-component-polish/run.py verify
UI_ENGINE=webkit uv run python handoff/rounds/305-frontend-component-polish/run.py webkit
git diff --check origin/main HEAD
