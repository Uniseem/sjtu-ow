# 259 生产停机割接正式执行与新栈全面上线报告

## 1. 执行概述
依据用户指令「那就正式替换」以及架构设计总纲（`docs/rewrite-research/12-architecture.md` 8.4）与生产割接剧本（`docs/cutover.md`），我们在 2026-10-09 正式对正式站（VPS `169.58.217.180`，端口 22887）执行了停机割接流水线。
新栈（Vue 3 SSR + Go 1.26 + SQLite WAL + Caddy 反代集群）已正式上线并全面接管所有生产流量，旧栈 Django 6 + Wagtail 8 容器已安全下线。

## 2. 停机割接指标与耗时测算
- **割接开始时间**：2026-10-09 13:45:34 (服务器时间)
- **割接完成时间**：2026-10-09 13:45:50 (服务器时间)
- **实际总停机耗时**：**16 秒**（远低于 15 分钟/900 秒维护窗口预算）
- **数据安全性**：
  - 生产数据库最终快照：`/root/sjtu-ow-backups/legacy-final-20261009134549.sqlite3`
  - 前置全量配置备份：`/root/cutover-safety-backup/`（含 `.env`、`db-pre-cutover.sqlite3`、`Caddyfile.vps` 等）

## 3. 数据一致性与对账结果（100% MATCH）
在割接流水线第 6 步，新栈自动执行了 `sjtuow reconcile` 全量数据对账自检：
- `PRAGMA integrity_check`: **[PASS]**
- `PRAGMA foreign_key_check`: **[PASS]**
- 12 项业务实体表行数对比如下：

| 实体 | 新表 | 旧表 | 新库行数 | 旧库行数 | 状态 |
|---|---|---|---|---|---|
| 用户账号 | users | accounts_user | 1 | 1 | **MATCH** |
| 战队 | teams | teams_team | 1 | 1 | **MATCH** |
| 战队成员 | team_memberships | teams_teammembership | 0 | 0 | **MATCH** |
| 赛事 | tournaments | tournaments_tournament | 1 | 1 | **MATCH** |
| 赛事报名 | registrations | tournaments_registration | 0 | 0 | **MATCH** |
| 内战 | scrims | scrims_scrim | 1 | 1 | **MATCH** |
| 内战报名 | scrim_signups | scrims_scrimsignup | 0 | 0 | **MATCH** |
| 文章 | articles | content_articlepage | 1 | 1 | **MATCH** |
| 评论 | comments | comments_comment | 4 | 4 | **MATCH** |
| 图片母版 | images | wagtailimages_image | 479 | 479 | **MATCH** |
| 成员分组 | member_groups | members_membergroup | 1 | 1 | **MATCH** |
| 审核记录 | moderation_items | moderation_moderationitem | 0 | 0 | **MATCH** |

- **关键对象抽样比对**：
  - 用户 `ow4sjtu@126.com`: 新库 (super=1, active=1) vs 旧库 (super=1, active=1) -> match=true
  - 战队 #1: 新库「测试战队」vs 旧库「测试战队」-> match=true

## 4. 关键问题诊断与修复
1. **Docker Compose 项目名统一**：在 `cutover.sh` 中增加 `-p sjtu-ow`，避免容器卷因默认目录名 `deploy` 与宿主已有卷产生冲突告警；
2. **容器 ENTRYPOINT 参数调用**：修复 `Dockerfile.server` 中 ENTRYPOINT 指向与 `cutover.sh` 参数传递，移除重复二进制路径，并在容器内添加 `/usr/local/bin/sjtuow` 软链接；
3. **SSR 运行时零依赖打包**：在 `web/apps/site/vite.config.ts` 配置 `ssr: { noExternal: true }`，确保 Rollup 构建 `dist/server/server.js` 时将 `@unhead/vue`、`vue`、`vue-router` 等所有第三方依赖内联打包，使运行时镜像完全解耦 `node_modules`。

## 5. 生产上线验证与冒烟检查
1. **容器运行状态**：
   - `sjtu-ow-proxy-1`: Up (Caddy 反代，监听 22887 端口)
   - `sjtu-ow-server-1`: Up (healthy，Go API 核心，监听 8080)
   - `sjtu-ow-worker-1`: Up (Go 后台异步与定时任务服务)
   - `sjtu-ow-web-1`: Up (Vue 3 SSR 服务，监听 5173)
2. **健康检查 (`/healthz`)**：
   ```json
   HTTP/2 200 OK
   {"status":"ok","checks":{"database":{"ok":true},"disk":{"ok":true},"task_backlog":{"ok":true},"worker_heartbeat":{"ok":true}}}
   ```
3. **前台页面可达性**：
   - `https://sjtu.ow-shanghaiuniversity.com/` 返回 HTTP 200，包含标准 `ow-state` 数据块与客户端 hydration 资源；
   - 严格 CSP 响应头完整输出，禁止内联脚本；
   - 栏目路由（`/tournaments/`、`/teams/`、`/members/`、`/scrims/`）与尾部斜杠重定向均正常生效；
   - 公开 API（`/api/session` 返回 `{"user":null}`、`/api/teams` 返回战队列表结构）响应迅速正确。

## 6. 后续建议
1. 观察生产服务器资源消耗与容器日志；
2. 旧站镜像与只读数据库快照建议在宿主机 `/root/sjtu-ow-backups/` 保留两周；
3. 后续根据 12 号文档规划清理旧版 Django 代码与依赖。
