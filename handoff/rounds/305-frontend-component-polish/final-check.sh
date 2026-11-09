#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
(
  cd web
  pnpm install --frozen-lockfile
  pnpm test
)
(
  cd web/apps/admin
  node browser-check.mjs /usr/bin/chromium
)
UI_PROBE_ONLY=1 uv run python handoff/rounds/305-frontend-component-polish/run.py final-probe
UI_ENGINE=webkit uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-final
POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py images
UI_ENGINE=webkit POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-images
node handoff/rounds/305-frontend-component-polish/inventory.mjs /srv/build/sjtu-ow/305-inventory
git diff --check origin/main HEAD
