#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
bash handoff/rounds/305-frontend-component-polish/prepare-webkit.sh
UI_ENGINE=webkit POLISH_PLAYWRIGHT=/srv/build/sjtu-ow/305-webkit-1.63.0 uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-163
POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py images-final
UI_ENGINE=webkit POLISH_PLAYWRIGHT=/srv/build/sjtu-ow/305-webkit-1.63.0 POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-images-163
git diff --check origin/main HEAD
