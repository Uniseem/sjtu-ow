#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
export TMPDIR=/srv/sjtu-ow-check/tmp/300-operations
export GOTMPDIR=$TMPDIR/go
mkdir -p "$GOTMPDIR"
if [ "${1:-}" != "--reuse-builds" ]; then
  cd web
  pnpm install --frozen-lockfile
  pnpm --filter @sjtu-ow/site build
  pnpm --filter @sjtu-ow/admin build
  cd ..
fi
uv run python handoff/rounds/300-webkit-final-operations/run.py "${2:-all}"
