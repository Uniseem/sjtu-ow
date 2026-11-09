#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
(
  cd web
  pnpm test
)
bash handoff/rounds/305-frontend-component-polish/finish-check.sh
