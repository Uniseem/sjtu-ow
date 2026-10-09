# 251 M7 通知与日历订阅

## 背景

M6、审核记录（250）完成后，进入 M7 通知域。在 250 中发现：
1. 注册表以前没有给登录用户的写请求开启待发信批次，动作产生的邮件直接入队，与规则 206 不符。
2. M4 的 `BroadcastArticle` 只是记录收件人数而没有真正发信。
3. 规则 73–79、206–216 涉及待发信批次处理、确认发信页、全员公告广播（文章/赛事/内战统一模型）、退订体系（签名链接、RFC 8058 一键退订、用户开关）、以及手机日历订阅（ICS 生成、地址版本作废与轮换）。

## 本轮范围

做：
1. 数据库迁移 00015：
   - `users.accepts_announcements`（默认 1，活动通知开关）；
   - `users.calendar_version`（默认 0，日历订阅地址版本）；
   - 重构 `broadcasts` 表为统一模型（`kind IN ('article', 'tournament', 'scrim')`，`audience IN ('everyone', 'participants')`，支持 `waits_for_publish` 定时上线通知）。
2. 待发信机制（规则 206–208）：
   - `api.Registry` 针对登录用户非 GET 请求初始化 `outbox.Open(viewer.ID)`；
   - 动作若产生信件，在响应 JSON 中追加 `letters: {batch, count}`；若用户在请求中注销则由系统代发（规则 208）；
   - `notify.Service` 待发信确认接口：`Held`、`DecideHeld`（支持勾选部分发送与全部跳过，防重复认领）、`Waiting`（7 天内有效任务汇总）；
   - 待发信行保留 30 天，超时由 worker 04:00 夜任务清理。
3. 全员公告广播（规则 73–79）：
   - 统一接口：`Status` 与 `Announce`（支持文章、赛事、内战）；
   - 规则校验：30 分钟冷却（提示上次北京时间）、已发布或定时发布前置检查、SMTP 配置前置检查；
   - 定时上线通知（规则 74）：文章定时发布时登记 `waits_for_publish = 1`，文章正式发布时由 `SendWaiting` 触发下发任务；
   - 异步分发任务 `notify.deliver`：发送时重新计算活跃且已验证且开启通知的成员，逐人生成带独立退订链接的邮件；
   - 历史次数提示 `RepeatNotice`（规则 77）：从第二封起在邮件中标注「之前已经发过 N 次」；
   - 统一接入 `audit_log` 审计记录。
4. 退订体系（规则 212–213）：
   - 签名退订 Token（`djsign.Dumps` 配合 `UnsubscribeSalt`）；
   - 前台查看与退订接口：`GET/POST /api/announcements/unsubscribe/{token}`；
   - 个人偏好设置：`GET/POST /api/me/announcements`；
   - 邮件客户端 RFC 8058 一键退订：`POST /unsubscribe/{token}/{$}`。
5. 我的安排与手机日历订阅（规则 216、设计 5.2、13.5）：
   - `agenda.Service`：汇总内战（进行中或未来 6 小时内）与赛事（已报名或散人池），支持状态文本与格式化；
   - `GET /api/me/agenda`：首页「我的安排」最多展示 4 项；
   - `GET /api/me/calendar` 与 `POST /api/me/calendar/renew`：日历订阅地址与重置密钥（旧地址立刻失效）；
   - `GET /calendar/{file}`：无状态公开 ICS 文件服务，RFC 5545 格式生成与 75 字节平滑折叠，带 `CalendarFeed` 限流（30次/分/IP）。
6. 存量导入与 apigen：
   - `accounts.ImportLegacyAccounts` 支持旧库导入 `accepts_announcements` 与 `calendar_version`；
   - `sjtuow apigen` 更新前端 TypeScript API Client。

不做：
- 前台 Vue 页面交互（M8 全面排版落地）。

## 验收

- 测试机上 Go 测试（`go test ./...`）、静态检查（`gofmt`, `go vet`, `staticcheck`, `govulncheck`）、前端测试（`pnpm test`）整组全绿。
- `apigen` 生成内容与仓库严格一致。
