#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
phase=${1:-after}
node handoff/rounds/305-frontend-component-polish/inventory.mjs /srv/build/sjtu-ow/305-inventory
if [ "$phase" = baseline ]; then
  cd web
  pnpm install --frozen-lockfile
  pnpm --filter @sjtu-ow/site build
  pnpm --filter @sjtu-ow/admin build
  cd ..
else
  sh scripts/check.sh
fi
uv run python handoff/rounds/305-frontend-component-polish/run.py "$phase"
