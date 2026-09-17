# 045 实现报告

## 结论

**完成本地部分，CI 结果以推送后的 run 为准**（报告随提交推送，推送之后才有 CI）。`/healthz` 503 的原因确认是 GitHub 托管机器的磁盘只剩 17.8%；两条测数据库探活的测试里把磁盘固定成健康，不再依赖机器。

## 原因

044 推送后的 CI（run 35242003672），`/healthz` 返回的完整内容：

```
{"status": "error", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": false, "detail": "free space 17.8% is at or below 20%"}, "worker_heartbeat": {"ok": true, "detail": "ok (0s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
```

四项里只有磁盘没过。044 的推测对了，但**这次是有证据之后才改**。

那次 CI 的各步：

```
success Ruff
success Build Tailwind CSS
failure Tests
skipped Missing migrations
skipped Production deploy check
skipped Error pages match templates
skipped Docker image
```

`Build Tailwind CSS` 通过，`app.css` 那条不再失败（`2 failed, 658 passed`，比 044 之前少一条）。

## 修法

这两条测试测的是数据库探活：正常时 200、数据库被锁时仍然 200。磁盘阈值 044 已经有独立的边界测试。所以在这两条测试里用同一个假的 `disk_usage` 把磁盘固定成剩 50%。

**没改的**：`core/health.py`、20% 阈值、其他测试。

生产服务器上健康检查照常读真实磁盘——磁盘低于 20% 时 `/healthz` 返回 503 正是设计 16.6 要的。CI 机器磁盘紧张不代表代码有问题。

## 本地复现

在 `conftest.py` 里临时加一个自动生效的 fixture，把磁盘模拟成 CI 机器的 17.8%，分别跑 044 版和 045 版的测试文件：

```
044 版测试 + 模拟 17.8%: 2 failed, 8 passed in 0.57s ['core/tests/test_pages.py::test_healthz_returns_200', 'core/tests/test_pages.py::test_healthz_returns_200_when_database_is_busy']
045 版测试 + 模拟 17.8%: 10 passed in 0.46s []
已还原: True
```

044 版失败的正好是 CI 上失败的那两条。

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
211 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
660 passed in 47.14s
```

## 还没在 CI 上验证过的

测试步骤之后的四步**在 GitHub 上从来没执行到过**：迁移检查、生产部署检查、错误页对比、`docker build`。前三步本地每轮都跑；`docker build` 本地 022 轮跑过。这次推送是它们第一次在 CI 上跑。

## 改动文件

```
core/tests/test_pages.py                 两条测试固定磁盘；辅助函数挪到文件开头
handoff/STATUS.md
handoff/rounds/045-ci-green/             本轮三份
```
