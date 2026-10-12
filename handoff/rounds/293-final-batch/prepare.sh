#!/usr/bin/env bash
# Test-host-only preparation, after the complete initial coding stage.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
cd "$ROOT/server"
gofmt -w cmd/sjtuow/main.go internal/accounts/api.go internal/accounts/api_test.go internal/accounts/service.go internal/accounts/contact_concurrency_test.go internal/content/api.go internal/ops/reconcile.go internal/ops/reconcile_test.go internal/platform/storage/s3.go internal/platform/storage/s3_test.go internal/settings/import.go internal/mailpreview/module.go
go run ./cmd/sjtuow apigen
cd "$ROOT/web"
pnpm install --lockfile-only
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps webkit
echo FINAL-PREPARE-OK
