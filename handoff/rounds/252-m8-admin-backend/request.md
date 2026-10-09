# 252 M8 后台管理 API 与平台全量服务补齐

## 背景

在 M7（通知与日程订阅）完成后，进入 M8。现行 Django 后台拥有全套管理功能（`docs/admin.md`、`docs/admin-inventory.md`、`docs/rewrite-research/05-business-rules.md`）：
1. 全站设置（SMTP 邮件配置、栏目横幅图片、社区成立日期、战队上限、提醒小时数、AI 内容审核接口与每日上限）；
2. 敏感字段加密存储（Fernet 对称加密，出参脱敏）；
3. 平台媒体库管理与图片上传（支持 base64 DataURL 与 multipart FormData）；
4. 用户头像上传（每日 5 次限流、自动清理旧图）、撤回与管理员下架违规头像；战队队标上传与清理；
5. 全站审计日志查询（按动作、操作人、对象类型、时间范围过滤，带操作人昵称联查）；
6. 干部待办聚合（待发信批次、未审赛事报名、散人待编排、超期未结赛事、未分队内战、无队长战队、AI 巡查异常与 Worker 心跳）；
7. 活动数据统计与导出（学年/最近 30 天预设、内战/赛事逐场事件列表、宏观数据汇总、Excel UTF-8 BOM CSV 导出）；
8. 干部手册（按角色板块过滤呈现）；
9. 评论管理（全站跨文章检索、筛选隐藏与置顶）。

## 本轮范围

做：
1. 数据库迁移 00016：
   - `users.avatar_image_id` 外键关联 `images`；
   - `avatar_submissions` 头像审核记录表；
   - 补齐 `site_settings` 全量字段（SMTP 凭证、各栏目横幅、站点简介、成立日期、AI 内容审核配置）。
2. 媒体库管理与上传接口：
   - `GET /api/admin/images`（支持按集合、关键字筛选与分页）；
   - `GET /api/admin/image-collections`；
   - `POST /api/admin/images/upload`（JSON DataURL/base64）；
   - `POST /api/admin/images/upload-file`（multipart/form-data 原生文件上传）。
3. 头像与队标服务：
   - `POST /api/me/avatar`（按人每日 5 次限流，更新 `users.avatar_image_id` 并自动清理旧头像图片）；
   - `DELETE /api/me/avatar`；
   - `GET /api/admin/avatars`；
   - `POST /api/admin/avatars/{id}/take-down`（下架头像清空当前头像并在记录中标记说明）；
   - `POST /api/teams/{id}/logo`（队长/超管上传队标，自动清理旧队标）。
4. 全站设置服务与邮件测试：
   - `GET /api/admin/settings`（超管专享，SMTP 密码与审核密钥使用 Fernet 解密验证后脱敏输出 `has_*` 标志）；
   - `PATCH /api/admin/settings`（局部更新，密码留空不覆盖，写入 `audit_log`）；
   - `POST /api/admin/settings/test-email`（发送测试邮件至当前管理员邮箱）。
5. 审计日志查询：
   - `GET /api/admin/log`（超管专享，多维度筛选，联查操作人昵称与邮箱）。
6. 后台待办聚合：
   - `GET /api/admin/todo`（按干部角色聚合全站各模块待办与异常）。
7. 活动数据统计与导出：
   - `GET /api/admin/activity`（上海时区学年预设与逐场汇总）；
   - `GET /api/admin/activity/export`（带 UTF-8 BOM 的 CSV 导出）。
8. 干部手册：
   - `GET /api/admin/manual`（按角色/能力过滤板块）。
9. 评论管理接口：
   - `GET /api/admin/comments`（跨文章搜索与隐藏/置顶过滤）。
10. 存量旧库数据导入与 Apigen：
    - 导入 Django `accounts_user.avatar_id` 与 `accounts_avatarsubmission`；
    - 导入 Django `core_sitesettings` 全站配置；
    - `sjtuow apigen` 更新前端 TypeScript API Client。

不做：
- 后台 Vue 页面交互与组件开发（M8 下半部分与前端全面对齐）。

## 验收

- 测试机上 Go 测试（`go test ./...`）、静态检查（`gofmt`, `go vet`, `staticcheck`, `govulncheck`）、前端测试（`pnpm test`）整组全绿。
- `apigen` 生成内容与仓库代码无 diff。
