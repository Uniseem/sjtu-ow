#!/usr/bin/env bash
# Test-host-only source formatting and generator; no hand-written generated files.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT/server"
gofmt -w .
go run ./cmd/sjtuow apigen
cd "$ROOT"
git diff --name-only -- server web/packages/api/src/gen docs/api-reference.md > /tmp/sjtuow-294-generated-files
if [[ -s /tmp/sjtuow-294-generated-files ]]; then
  tar -cf /tmp/sjtuow-294-generated.tar -T /tmp/sjtuow-294-generated-files
else
  tar -cf /tmp/sjtuow-294-generated.tar --files-from /dev/null
fi
printf 'FINAL-PREPARE-OK files=%s\n' "$(wc -l < /tmp/sjtuow-294-generated-files)"
