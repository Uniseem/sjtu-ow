#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT/server"
gofmt -w internal cmd/sjtuow
go run ./cmd/sjtuow apigen
echo FINAL-PREPARE-OK
