#!/bin/sh
# 222 轮：在测试机 /srv/sjtu-ow-check 下装 Go、Node 24、pnpm 和 Go 的两个检查工具
# （docs/rewrite-research/13-ideas-and-followups.md C 节）。不动系统自带的 Node 20；
# 压缩包都核对官方 sha256；脚本可以重复跑（装好的跳过）。
# 注意：npm / pnpm 的 shebang 是 /usr/bin/env node，必须把 node24/bin 放在 PATH
# 最前面再调，否则会落到系统 Node 20 上（第一次就栽在这里）。
set -eu
cd /srv/sjtu-ow-check
export PATH="$PWD/node24/bin:$PATH"

GO_TGZ=go1.26.8.linux-amd64.tar.gz
GO_SHA256=d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b
NODE_VER=v24.13.0
NODE_TGZ=node-$NODE_VER-linux-x64.tar.xz
NODE_SHA256=e798599612f4bb71333a3397ab0d095fd62214e115aea45aa858a145fc72d67e
PNPM_VER=11.20.0
STATICCHECK_VER=v0.8.1
GOVULNCHECK_VER=v1.8.0

echo "== Go 1.26.5"
if ! ./go/bin/go version 2>/dev/null | grep -q go1.26.8; then
  [ -f "$GO_TGZ" ] || curl -fsSLO "https://go.dev/dl/$GO_TGZ"
  echo "$GO_SHA256  $GO_TGZ" | sha256sum -c -
  rm -rf go && tar -xzf "$GO_TGZ"
fi
./go/bin/go version

echo "== Node $NODE_VER + pnpm"
if ! ./node24/bin/node --version 2>/dev/null | grep -q "$NODE_VER"; then
  [ -f "$NODE_TGZ" ] || curl -fsSLO "https://nodejs.org/dist/$NODE_VER/$NODE_TGZ"
  echo "$NODE_SHA256  $NODE_TGZ" | sha256sum -c -
  rm -rf node24 && mkdir node24
  tar -xJf "$NODE_TGZ" -C node24 --strip-components=1
fi
./node24/bin/node --version
./node24/bin/npm install -g pnpm@$PNPM_VER --prefix "$PWD/node24" --no-fund --no-audit >/dev/null
node --version && pnpm --version

echo "== staticcheck / govulncheck（go install，模块校验和由 sumdb 核）"
export GOROOT="$PWD/go" GOPATH="$PWD/gopath" GOCACHE="$PWD/gocache" GOMODCACHE="$PWD/gomodcache" GOBIN="$PWD/gobin"
./go/bin/go install honnef.co/go/tools/cmd/staticcheck@$STATICCHECK_VER
./go/bin/go install golang.org/x/vuln/cmd/govulncheck@$GOVULNCHECK_VER
./gobin/staticcheck -version
./gobin/govulncheck -version 2>&1 | head -1

echo "== 系统 Node 没被动"
command -v node && node --version

echo INSTALL-OK
