# 003 复核结果

## 结论

**通过。** R1、R2、R3 都按要求修好，我独立验证过每一条。M0 到此完成，可以进 M1。

## 验证记录

| 项目 | 我的验证方式 | 结果 |
|---|---|---|
| R1 忙 vs 坏 | 自己写脚本：第二个连接 `BEGIN IMMEDIATE` 占住写锁后请求 `/healthz` | **HTTP 200、0.24 秒**，detail 为 `busy: another write in progress`；释放后 0.00 秒返回 ok。对比 002 时的 503 + 5.2 秒，问题解决 |
| R1 真故障 | 复制数据库到只读目录、`chmod 444`，直接调用 `check_database()` | 返回 `(False, 'attempt to write a readonly database')`，整体 `ok=False` → 503 ✅ |
| R1 探针表 | 读代码 + 迁移 | 用 `core.HealthProbe` 专用表，不再写 `django_content_type`；`PRAGMA busy_timeout=200` 前后有保存和恢复 |
| R2 错误页样式 | `DEBUG=False` 起服务，浏览器打开不存在的地址 | 页面有完整布局和按钮样式，**控制台 0 条报错**（截图确认） |
| R2 单一数据源 | grep 产物 | `deploy/error_pages/` 只剩 `maintenance.html`，不含 `/static/`、`<link>`、`<script>`，且包含 `error.css` 的特征选择器 `.actions a.secondary` |
| R2 CSP 未放宽 | 读 settings | `SECURE_CSP` 原样未改 ✅ |
| R3 改名 | 全仓库 grep `WAGTAILADMIN_PATH_PREFIX` | 无残留 |
| 首页 | 浏览器控制台 | 0 条报错 |
| ruff / pytest / makemigrations / check --deploy | 本地重跑 | 全通过，10 个测试，0 issues |
| 错误页漂移 | 本地重新生成后看 git 状态 | 无漂移 |
| Caddyfile | `docker run caddy validate` | `Valid configuration` |
| Docker 镜像 | `docker images` | `dc37ba2ba386`，4 分钟前构建，与报告一致 |
| git | `git status` | 工作区干净，提交信息 `003: distinguish sqlite busy from failure and restore error-page CSS` |

## 必须修

无。

## 建议修

无。以下两点记录备查，不需要本轮处理：

- `_is_sqlite_busy` 靠错误信息里的 `database is locked` / `database is busy` 关键字判断。这是 SQLite 的稳定措辞，可以接受；换数据库或换驱动时要重新确认
- 探活仍然会短暂抢一次全库写锁（任何真实写入都会），但等待上限 200 毫秒、忙也不算故障，影响可以忽略

## 认可的判断

- R3.2 保持 CI 现状的理由成立：workflow 本来就只在 push 到 main 和 PR 时触发，再拆 job 没有收益
- 删掉另外 4 份静态错误页产物是对的：Caddy 只需要维护页，少一份产物就少一处漂移来源
- 「无尾部斜杠的路径先 301 再 404」的观察正确，那是 `APPEND_SLASH` 的正常行为

## 文档更新

`docs/design.md` 升到 **v1.5.3**：按报告里提的偏差，在 12.4 节补了 **12.4.7 HealthProbe（健康检查探针表）**，和 16.6 节「写入专用探针表再回滚」对齐。
