#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py images-finished
UI_ENGINE=webkit POLISH_PLAYWRIGHT=/srv/build/sjtu-ow/305-webkit-1.63.0 POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-images-finished
node handoff/rounds/305-frontend-component-polish/inventory.mjs /srv/build/sjtu-ow/305-inventory
git diff --check origin/main HEAD
