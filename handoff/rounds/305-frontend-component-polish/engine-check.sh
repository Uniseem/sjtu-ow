#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
uv run python handoff/rounds/305-frontend-component-polish/mutate-toast.py
UI_ENGINE=webkit POLISH_BROWSER=csp-origin.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py csp-origin
UI_ENGINE=webkit uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-verified
POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py images-verified
UI_ENGINE=webkit POLISH_BROWSER=image-check.mjs uv run python handoff/rounds/305-frontend-component-polish/run.py webkit-images-verified
