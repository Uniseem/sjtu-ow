#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT/server"
gofmt -w cmd/sjtuow internal/accounts internal/content internal/ops internal/platform/audit internal/platform/auth internal/platform/media internal/backoffice internal/members internal/teams internal/tournaments internal/scrims internal/notify internal/manual internal/mailpreview
go run ./cmd/sjtuow apigen
echo FINAL-PREPARE-OK
