# 045 CI 转绿

## 背景

044 让 `/healthz` 两条测试失败时打印完整响应。044 推送后的 CI（run 35242003672）：

```
AssertionError: {"status": "error", "checks": {"database": {"ok": true, "detail": "ok"}, "disk": {"ok": false, "detail": "free space 17.8% is at or below 20%"}, "worker_heartbeat": {"ok": true, "detail": "ok (0s ago)", "affects_status": true}, "task_backlog": {"ok": true, "detail": "ok", "affects_status": true}}}
============= 2 failed, 658 passed in 137.35s (0:02:17) ===================
```

**原因确认是磁盘**：GitHub 托管机器剩 17.8%，低于设计 16.6 的 20%。数据库、心跳、积压任务都正常——包括「数据库被锁」那条，探活正确识别成 `busy`。`app.css` 那条 044 已经修好（`Build Tailwind CSS` 步骤通过，体积测试通过）。

## 任务

这两条测试测的是**数据库探活**（正常时 200、被锁时仍 200），磁盘只是顺带。044 已经给磁盘阈值补了独立的边界测试（假的 `disk_usage`），所以这两条测试里也把磁盘固定成健康，**不再依赖跑测试那台机器还剩多少空间**。

- 不改阈值，不改 `core/health.py`
- 不跳过测试

## 验收标准

1. 本地四项检查干净
2. **推送后 GitHub 上的 CI 全绿**，贴 run 编号和每一步的结果（包括之前从没跑到过的迁移检查、部署检查、错误页、`docker build`）
3. git 提交以 `045:` 开头
