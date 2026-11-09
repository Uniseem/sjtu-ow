#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
gofmt -w server/internal/scrims/api_test.go server/internal/tournaments/api_test.go
cd server
go test ./internal/scrims ./internal/tournaments -run '^TestRoutesAndGates$' -count=1
