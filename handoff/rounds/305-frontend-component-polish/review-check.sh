#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
(
  cd web
  pnpm test
)
(
  cd web/apps/admin
  node browser-check.mjs /usr/bin/chromium
)
POLISH_BROWSER=management-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py management
POLISH_BROWSER=negative-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py negative
uv run python handoff/rounds/305-frontend-component-polish/mutate-toast.py
git diff --check origin/main HEAD
