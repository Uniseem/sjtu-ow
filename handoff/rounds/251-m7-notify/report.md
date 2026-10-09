# 251 实现报告

## 结论

完成。M7 通知域（待发信批次与确认、统一公告广播、退订体系）与日程/手机日历订阅（我的安排、ICS 生成、地址轮换作废与限流）全量完成；存量旧库字段导入对齐；`sjtuow apigen` 更新客户端生成物；测试机整组检查通过。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 迁移 00015 | `users.accepts_announcements`（默认 1）、`users.calendar_version`（默认 0）；重构 `broadcasts` 表为多类型通用模型（文章、赛事、内战），支持 `waits_for_publish` 索引与状态控制 |
| 注册表待发信批次 R206–208 | `api.Registry` 在登录用户写操作时开启 `outbox.Open(viewer.ID)`；写操作产生信件时在响应 JSON 包装 `letters: {batch, count}`；用户在请求中注销时触发 `outbox.SendAll` 系统代发 |
| 待发信确认页接口 R206–208 | `GET /api/letters/{batch}` 读批次（区分 waiting/done/expired，7天过期）；`POST /api/letters/{batch}` 勾选发送或全部跳过（原子防重复认领）；`GET /api/letters` 汇总 7 天内待办；worker 04:00 清理 30 天前记录 |
| 统一公告广播 R073–079 | `GET/POST /api/admin/announce/{kind}/{id}` 支持文章、赛事、内战；30 分钟冷却（精准提示上次北京时间）；发布状态前置检查；SMTP 未配置友好提示拦截；第 2 封起自动注入「之前已经发过 N 次」提示 |
| 定时上线触发 R074 | 文章安排定时上线时挂起 `waits_for_publish = 1`；文章定时发布或即时发布上线那一刻由 `SendWaiting` 条件触发唤醒并入队投递任务 |
| 异步按人投递与退订链接 R076 | 任务 `notify.deliver` 在投递执行时动态计算目标成员（活跃、已验证、接受通知）；逐人生成独立签名退订链接；更新实际投递人数；记录 `audit_log` |
| 退订体系 R212–213 | `djsign` 生成签名令牌；`GET/POST /api/announcements/unsubscribe/{token}` 页面退订与状态回显；`GET/POST /api/me/announcements` 个人设置；RFC 8058 `POST /unsubscribe/{token}/{$}` 邮件客户端一键退订，非 JSON 路由统一接入限流 |
| 我的安排 R216、设计 5.2 | `GET /api/me/agenda` 聚合内战（进行中或未来 6 小时内）与赛事（已报名或等待编队），按时间升序排列，首页限制展示最多 4 条 |
| 手机日历订阅 R216、设计 13.5 | `GET /api/me/calendar` 返回 URL 与 Webcal；`POST /api/me/calendar/renew` 递增版本立即使旧订阅地址失效；`GET /calendar/{file}` 服务 ICS 文件，严格遵循 RFC 5545 且超过 75 字节平滑按行折叠（不截断 UTF-8 字符），套用 `CalendarFeed` 限流（30次/分/IP） |
| 存量旧库导入与 Apigen | `ImportLegacyAccounts` 补充 `accepts_announcements` 与 `calendar_version` 读取与写入；`sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts` |

## 设计偏差

- 现行站的日历订阅在用户重置时使用递增整数版本（13.5 节）；新栈完全沿用该机制并落表 `users.calendar_version`，既兼容旧地址，又能在换地址时瞬间使旧地址失效。
- 原 M4 `BroadcastArticle` 被通用通知机制完全接管并移除冗余的 `/api/admin/articles/{id}/broadcast` 接口，全站使用统一的 `/api/admin/announce/{kind}/{id}` 路由。

## 验收输出

测试机 kvm17243（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-140028-f4a35e0.log`）：
- Go（新栈）：
  - `gofmt -l .`：无待格式化文件
  - `go vet ./...`：通过
  - `staticcheck ./...`：通过
  - `govulncheck ./...`：0 个漏洞（无受影响依赖）
  - `go test ./...`：全包通过，包括新增的 `internal/notify` 与 `internal/agenda`
  - `go run ./cmd/sjtuow apigen`：无 git diff
- Web（新栈）：
  - `pnpm install --frozen-lockfile`：通过
  - `pnpm test`：通过（7 个测试文件、47 个测试用例全过；首页壳 gzip: HTML 2508 + CSS 17870 + JS 53152 = 73530 字节，远低于 307200 上限，BUDGET-OK）
- 退出码 0，全部通过。

## 改动文件

- `server/db/migrations/00015_announcements.sql`
- `server/internal/platform/api/registry.go`
- `server/internal/platform/outbox/outbox.go`
- `server/internal/platform/ratelimit/limits.go`、`limits_test.go`
- `server/internal/notify/`（announce.go, letters.go, unsubscribe.go, api.go, notify_test.go）
- `server/internal/agenda/`（agenda.go, ics.go, api.go, agenda_test.go）
- `server/internal/content/`（announce.go, api.go, model.go, service.go, store.go, m4_full_test.go）
- `server/internal/tournaments/`（announce.go, service.go）
- `server/internal/scrims/`（announce.go, service.go）
- `server/internal/accounts/`（import.go, m3_full_test.go）
- `server/cmd/sjtuow/main.go`
- `web/packages/api/src/gen/index.ts`
- `handoff/rounds/251-m7-notify/`（本目录）
