# 252 实现报告

## 结论

完成。M8 后台管理 API 与平台全量服务补齐（全站设置、敏感信息加密与脱敏、平台图片库与文件上传、头像与队标上传流转及冗余清理、审计日志多维检索、干部待办聚合、活动数据分析与 CSV 导出、干部手册、评论管理、旧库存量数据导入以及 `sjtuow apigen` 客户端更新）；测试机整组检查通过。

## 逐条结果

| 要求 | 结果 |
|---|---|
| 迁移 00016 | `users.avatar_image_id`、`avatar_submissions` 表；`site_settings` 扩充 SMTP 凭证、各栏目横幅 ID、简介、成立日期、AI 审核完整配置参数 |
| 全站设置服务 | `GET /api/admin/settings` 返回全量配置，敏感密码/密钥以 `has_*` 脱敏输出；`PATCH /api/admin/settings` 局部更新，空值保留旧密钥，Fernet 密文写入并记录审计日志；`POST /api/admin/settings/test-email` 验证配置发信给当前管理员 |
| 媒体与图片上传 | `GET /api/admin/images`（按集合、分类、关键字检索与分页）、`GET /api/admin/image-collections`、`POST /api/admin/images/upload`（JSON DataURL）、`POST /api/admin/images/upload-file`（multipart/form-data 文件上传） |
| 头像与队标服务 | `POST /api/me/avatar`（按人每日 5 次限流，更新头像并自动删除旧头像母版与缩略图）、`DELETE /api/me/avatar`、`GET /api/admin/avatars`、`POST /api/admin/avatars/{id}/take-down`（下架头像设 NULL 并标记审核说明）；`POST /api/teams/{id}/logo`（队长/超管上传队标并自动清空旧队标） |
| 审计日志查询 | `GET /api/admin/log` 支持 `action`、`actor_id`、`object_type`、`since`、`until` 多维筛选，联查操作人昵称与邮箱，按 ID 倒序分页 |
| 干部待办聚合 | `GET /api/admin/todo` 汇总待确认发信批次、未审核赛事报名、待编排散人池、超期未完赛、未分队内战、无队长战队、AI 巡查异常与 Worker 进程存活状态 |
| 活动数据统计与导出 | `GET /api/admin/activity` 支持上海时区学年预设与逐场内战/赛事列表及宏观汇总；`GET /api/admin/activity/export` 输出包含 UTF-8 BOM 兼容 Excel 的标准 CSV |
| 干部手册与评论管理 | `GET /api/admin/manual` 按角色能力输出板块；`GET /api/admin/comments` 跨文章检索评论正文并支持隐藏与置顶过滤 |
## 验收输出

测试机 kvm17243（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-145056-62f317f.log`）：
- Go（新栈）：
  - `gofmt -l .`：无待格式化文件
  - `go vet ./...`：通过
  - `staticcheck ./...`：通过
  - `govulncheck ./...`：0 个漏洞（无受影响依赖）
  - `go test ./...`：全包通过，包括新增的 `internal/settings`、`internal/activity`、`internal/todo`、`internal/platform/audit` 及头像上传测试
  - `go run ./cmd/sjtuow apigen`：无 git diff
- Web（新栈）：
  - `pnpm install --frozen-lockfile`：通过
  - `pnpm test`：通过（7 个测试文件、47 个测试用例全过；首页壳 gzip: HTML 2508 + CSS 17870 + JS 53152 = 73530 字节，远低于 307200 上限，BUDGET-OK）
- 退出码 0，全部通过。

## 改动文件

- `server/db/migrations/00016_site_settings_and_avatars.sql`
- `server/cmd/sjtuow/main.go`
- `server/internal/settings/`（settings.go, api.go, import.go, settings_test.go）
- `server/internal/platform/audit/`（audit.go, api.go, audit_test.go）
- `server/internal/platform/media/`（media.go, api.go）
- `server/internal/platform/ratelimit/limits.go`
- `server/internal/accounts/`（model.go, store.go, service.go, api.go, import.go, avatar_test.go）
- `server/internal/teams/`（service.go, api.go）
- `server/internal/comments/`（store.go, service.go, api.go）
- `server/internal/todo/`（todo.go, api.go, todo_test.go）
- `server/internal/activity/`（activity.go, api.go, activity_test.go）
- `server/internal/manual/`（manual.go, api.go）
- `server/internal/app/ctx.go`
- `web/packages/api/src/gen/index.ts`
- `web/packages/api/src/gen/nav.ts`
- `handoff/rounds/252-m8-admin-backend/`（本目录）
