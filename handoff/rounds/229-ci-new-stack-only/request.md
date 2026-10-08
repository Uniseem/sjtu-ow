# 229 推送只测新栈

## 背景

用户看完每次推送的 CI 之后说：老架构后面也不更新了，只测新架构就行。

## 本轮范围

### 做

1. GitHub Actions 去掉现行站那一件（ruff、pytest、迁移、生产配置、错误页、Docker 镜像），只留 `server/` 的 gofmt、vet、staticcheck、govulncheck、go test。
2. `scripts/check.sh` 和测试机上的 `remote-check.sh` 整组跟 CI 一样，只跑新栈。现行站那一组从这两个脚本里拿掉，不再用开关打开。
3. `AGENTS.md`、`README.md` 里「和 CI 一致」的说法改过来。一条 Go 测试钉住「CI 里没有现行站的命令，脚本里现行站默认关着」。

### 不做

- 不删现行站的测试和 `check.sh` 里那一段。
- 不改正式站。
- `/healthz`、apigen、`serve` / `worker` 仍是下一轮。

## 验收标准

测试机上 `gofmt`、`go vet`、`staticcheck`、`govulncheck`、`go test ./...` 全绿。两处变异变红后恢复。不加依赖。
