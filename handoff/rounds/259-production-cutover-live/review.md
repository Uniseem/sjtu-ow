# 259 生产停机割接正式执行独立复核

## 复核依据
- `docs/rewrite-research/12-architecture.md` 8.4 节「割接流水线」
- `docs/cutover.md` 生产停机割接完整剧本
- `AGENTS.md` 硬规则与运维规约

## 检查项逐条复核

### 1. 停机维护窗口与业务连续性
- [x] **耗时达标**：割接脚本实测总停机耗时 16 秒，远低于设计上限 900 秒（15 分钟）。
- [x] **优雅切换**：旧栈 Django 容器停用后立即创建宿主最终只读快照，杜绝割接期间任何脏写。

### 2. 数据无损迁移与一致性红线
- [x] **快照存档**：备份快照 `/root/sjtu-ow-backups/legacy-final-20261009134549.sqlite3` 完整留存。
- [x] **对账 100% MATCH**：12 项业务实体全部 MATCH，表行数完全对齐。
- [x] **数据完整性通过**：`PRAGMA integrity_check` 与 `foreign_key_check` 均通过。
- [x] **关键数据抽样一致**：超管账号 `ow4sjtu@126.com` 权限属性匹配，战队数据匹配。

### 3. 集群健康与生产可达性
- [x] **所有服务正常运行**：`sjtu-ow-proxy-1`、`sjtu-ow-server-1`、`sjtu-ow-worker-1`、`sjtu-ow-web-1` 均在线。
- [x] **监控端点正常**：`/healthz` 响应 200 OK，返回 `database`、`disk`、`task_backlog`、`worker_heartbeat` 均为 true。
- [x] **外部反向代理互通**：外部域名 `https://sjtu.ow-shanghaiuniversity.com/` 正常提供 HTTPS 访问。
- [x] **安全策略合规**：Caddy 反向代理正确识别 WARP 内网 IP（`100.96.0.0/12`），前台页面正确注入严格 CSP 响应头。

### 4. 结论
生产停机割接执行圆满成功，系统状态健康稳定，符合上线归档要求。
