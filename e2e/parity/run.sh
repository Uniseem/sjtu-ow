#!/usr/bin/env bash
# 对拍的入口（docs/frontend-migration.md 9.2）：先构建新站，再跑 parity.py。
#   bash scripts/remote-check.sh run bash e2e/parity/run.sh [--only=前缀,…] [--wide] [--strict]
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
export PATH=/srv/sjtu-ow-check/go/bin:/srv/sjtu-ow-check/node24/bin:$PATH
cd "$ROOT/web"
pnpm install --frozen-lockfile >/dev/null
pnpm --filter @sjtu-ow/site build >/dev/null 2>&1
cd "$ROOT"
# 上一次没收干净的 Caddy 容器
docker rm -f ow-parity-caddy >/dev/null 2>&1 || true
exec uv run python e2e/parity/parity.py "$@"
