# 229 实现报告

## 结论

完成。每次推送和测试机整组都只跑新栈。2 处变异全部变红后恢复。

## 逐条结果

GitHub Actions 只留 `server/` 的 gofmt、vet、staticcheck、govulncheck、go test。`scripts/check.sh` 同一组。测试机 `remote-check.sh` 不带参数时就跑这份脚本，不再传分片、镜像或现行站开关。pytest、ruff、迁移、生产配置、错误页、Docker 镜像从这两处拿掉。

## 验收输出

全部在测试机上跑。变异和整组是同一趟。日志 `20261008-183157-1ffbdad`，退出码 0。gofmt、vet、staticcheck 没有输出，接着是 govulncheck 和测试。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/config	0.003s
两处变异全部变红后恢复
MUTATIONS-OK
== Go（新栈）
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/config	0.003s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.595s
== 全部通过
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A CI 又跑 pytest | 工作流里在 `go test` 后面加上 `uv run pytest` | CI 不该再跑现行站：uv run pytest |
| B 测试机整组又跑 pytest | `check.sh` 的 `go test` 后面加上 `uv run pytest -q` | check.sh 不该再跑现行站：uv run pytest |

## 设计偏差

没有。12 号文档里将来的 CI 还有 Web 和镜像，那是 M2、M9 的事。这轮只是现行站不再进每次检查。

## 未完成 / 顺带发现

- `/healthz`、apigen、`serve` / `worker` 还没做。

## 改动文件

- `.github/workflows/ci.yml`
- `scripts/check.sh`
- `scripts/remote-check.sh`
- `server/internal/platform/config/ci_test.go`
- `core/tests/test_check_script.py`
- `AGENTS.md`
- `README.md`
- `handoff/rounds/229-ci-new-stack-only/`
- `handoff/STATUS.md`
