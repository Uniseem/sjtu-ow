#!/bin/sh
# What a round has to pass before it is committed, in CI's order
# (.github/workflows/ci.yml). Linux, from the repository root:
#
#   sh scripts/check.sh
#
# 229 起只跑新栈。现行站的 pytest、ruff、迁移、镜像不在这里。
# scripts/remote-check.sh runs this on the test machine against the working tree.
set -eu

step() { printf '\n== %s (%s)\n' "$1" "$(date +%H:%M:%S)"; }

step "Go（新栈）"
# 写法和 CI 的 go 任务逐条一致。工具链在测试机的 PATH 里（remote-check.sh 导出）；
# 本地兜底跑时缺什么装什么。
if [ -f server/go.mod ] && command -v go >/dev/null 2>&1; then
  (
    cd server
    command -v staticcheck >/dev/null 2>&1 || go install honnef.co/go/tools/cmd/staticcheck@v0.8.1
    command -v govulncheck >/dev/null 2>&1 || go install golang.org/x/vuln/cmd/govulncheck@v1.8.0
    export PATH="$(go env GOPATH)/bin:$PATH"
    test -z "$(gofmt -l .)" || { echo "gofmt 要格式化的文件：$(gofmt -l .)"; exit 1; }
    go vet ./...
    staticcheck ./...
    govulncheck ./...
    go test ./...
    go run ./cmd/sjtuow apigen
    git diff --exit-code -- ../web/packages/api/src/gen
  )
else
  echo "（没有 server/go.mod 或找不到 go，跳过 Go 段）"
  exit 1
fi

step "Web（新栈）"
# 写法和 CI 的 web 任务逐条一致。测试机的 node24/bin 已经在 PATH 最前。
if [ -f web/package.json ]; then
  (
    cd web
    command -v pnpm >/dev/null 2>&1 || { corepack enable && corepack prepare pnpm@11.20.0 --activate; }
    pnpm install --frozen-lockfile
    pnpm test
  )
else
  echo "（没有 web/package.json）"
  exit 1
fi

step "全部通过"
