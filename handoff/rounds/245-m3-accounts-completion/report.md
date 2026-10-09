# 245 实现报告

## 结论

完成。按照用户「把 M3 一次性做完，少测试，多写代码」的指令，本轮一次性完整实现了 M3 账号域的所有剩余业务规则（R001–R042）、所有接口与数据存储、后台用户管理与角色能力控制、以及存量 Django 数据库导入工具（`sjtuow import`），使重构新栈的 M3 账号里程碑全量交付并闭环。

- **重新认证与邮箱修改**（规则 R006、R007、R349）：
  - `POST /api/auth/reauthenticate`：在 5 分钟重认证窗口内重输密码，在当前会话记录 `reauth_at`（限流 10次/分/人，`AuthReauthenticate`）。
  - `POST /api/auth/email/change`：严格检查会话重认证窗口（5 分钟内）；校验新邮箱格式与全站唯一性；向新邮箱发送 6 位验证码（15 分钟有效，试 3 次，限流 10次/分/人，`AuthManageEmail`）。
  - `POST /api/auth/email/change/confirm`：核验 6 位码；原子更新 `users.email` 与 `email_norm`，作废临时验证码。
- **个人资料、段位与联系方式**（规则 R016–R021）：
  - `GET /api/me/profile` 与 `PATCH /api/me/profile`：个人昵称（2–16 字）、宣言（≤30 字，正则严禁外链与顶级域名）、主玩位置、补位位置、公开段位开关；自动计算 `is_complete`（至少 1 个游戏 ID + 至少 1 种联系方式，作为报名前置条件）；公开段位为所有游戏 ID 最高分，>180 天标记过期。
  - `POST /api/me/game-accounts`、`PATCH /api/me/game-accounts/{id}`、`DELETE /api/me/game-accounts/{id}`：BattleTag 格式与全局唯一（大小写不敏感），上限 5 个；段位 0–40 整数。
  - `POST /api/me/contacts`、`DELETE /api/me/contacts/{id}`：QQ（5–11 位数字）、微信（6–20 字符）、中国大陆手机号（11 位 1 开头）、其他（≤64 字符）；每种类型限 1 条。
- **账号原地匿名化注销**（规则 R028–R032）：
  - `POST /api/auth/delete-account`：必须输入当前密码（限 5次/小时，`AccountDeleteTry`）；在任队长禁止注销；原地匿名化（`email` 改为 `deleted-{id}@deleted.invalid`，昵称改为「已注销用户」，密码置 `!`，清空 roles/is_sjtu/motto，`is_active=false`，`deactivation_note="用户自行注销"`）；级联清理游戏 ID、联系方式、单人规则、角色与待发信；作废全部会话并清除 Cookie。
- **账号停用与重新启用**（规则 R033–R036）：
  - `POST /api/admin/users/{id}/deactivate`：必须填写停用原因，停用后清空全部会话；
  - `POST /api/admin/users/{id}/activate`：重新启用清空停用原因；禁止启用已注销账号（`@deleted.invalid`）。
- **个人数据导出**（规则 R037–R038）：
  - `GET /api/me/export`：限 5次/小时，完整导出账号、游戏 ID、联系方式、角色等自有数据域。
- **后台用户管理与角色功能限制**（规则 R011、R039–R042）：
  - `GET /api/admin/users`：分页搜索用户；仅超管可见邮箱。
  - `GET /api/admin/users/{id}`：用户详情；仅超管及有 `CapContactsView` 者可见联系方式。
  - `PATCH /api/admin/users/{id}/roles`：配置用户角色（内容编辑、赛事管理员、内战管理员、认证作者）。
  - `PATCH /api/admin/users/{id}/rules`：配置单用户功能规则（优先于角色限制）。
  - `GET /api/admin/feature-role-restrictions` 与 `PUT /api/admin/feature-role-restrictions`：配置全站角色功能限制。
- **数据迁移与服务端命令**（12 号文档 8.1、规则 R015）：
  - `sjtuow import`：从现行 Django SQLite 导入用户、游戏 ID、联系方式、角色、功能限制与规则。
  - `sjtuow verify-email <email>`：服务端直接背书邮箱已验证，不发验证信。

## 设计变更与修订（先改文档再改代码）

1. **`docs/rewrite-research/05-business-rules.md`**：完成 R001–R042 逐条校验。
2. **`docs/rewrite-research/12-architecture.md`**：
   - 5.4、5.7、5.8、5.9 节：各接口及规则状态打钩。
   - 11.2 节：M3 里程碑状态更新为完成。
   - 15 节修订记录：增加 245 轮记录。

## 逐条结果

1. **数据库迁移**（`server/db/migrations/00009_profile_and_accounts.sql`）：
   - `users` 增加 `main_role`、`flex_roles`；
   - 创建 `game_accounts` 表（`battletag_norm` 全局唯一索引）；
   - 创建 `contacts` 表（`user_id, type` 复合唯一约束）；
   - 创建 `email_changes` 表（重认证及邮箱变更临时状态）。
2. **限流配置**（`server/internal/platform/ratelimit/limits.go`）：
   - 增加 `AuthReauthenticate`（10/分/人，allauth `reauthenticate 10/m/user`）；
   - 增加 `AuthManageEmail`（10/分/人，allauth `manage_email 10/m/user`）；
   - 增加 `AccountDeleteTry`（5/小时/人，注销尝试限流）；
   - `limits_test.go` 对照断言表同步更新通过。
3. **平台层扩展**：
   - `server/internal/platform/api/registry.go`：新增 `api.Put`。
   - `server/internal/platform/api/bind.go`：支持 GET 接口的 `query:"..."` 参数绑定。
   - `server/internal/platform/api/errors.go`：`Error()` 输出格式化 `Fields`，保留结构化诊断信息。
   - `server/internal/platform/auth/session.go`：增加 `DeleteAllTx` 支持在现有写事务内原子删除用户全部会话，消除嵌套事务死锁。
   - `server/internal/platform/db/timefmt.go`：`ParseUTC` 扩充对 Django 存量 SQLite 日期格式（空格分隔、无 T/Z、微秒可选）的兼容解析。
4. **服务层与存储层**（`server/internal/accounts/`）：
   - `model.go`：定义 GameAccount、Contact、联系方式常量及数据结构。
   - `ranks.go`：实现守望先锋段位换算、BattleTag 规范化与格式校验、联系方式正则与位数校验、宣言安全过滤（正则拦截域名/网址）、资料完整度判定与过期段位计算。
   - `store.go`：实现资料更新、游戏 ID CRUD、联系方式 CRUD、邮箱修改验证码记录、原地匿名化事务、停用与重新启用事务、用户列表与统计、角色与功能规则事务。
   - `service.go`：实现重新认证、改邮箱、个人资料修改、增删改游戏 ID、增删联系方式、注销（含队长拦截）、导出、停用启用、后台列表与详情（权限感知）、角色与功能限制配置、直接验证邮箱。
   - `api.go`：定义各操作 DTO，注册全部路由并配置守卫（Member、Superuser、CapContactsView）。
   - `import.go`：实现 `ImportLegacyAccounts`，编号严格沿用、时间规范化为 UTC、角色映射为新系统角色。
5. **CLI 工具**（`server/cmd/sjtuow/main.go`）：
   - 实现 `import`（只读连接旧库导入新库）与 `verify-email`（直接背书激活主邮箱）子命令。
6. **前端 SDK 代码生成**：
   - 运行 `sjtuow apigen` 导出全部新增接口类型定义及后台导航。
7. **测试套件**（`server/internal/accounts/m3_full_test.go`）：
   - `TestReauthenticateAndEmailChange`：测试 5 分钟重认证窗口、新邮箱发码、旧邮箱与未认证拦截、确认换绑邮箱。
   - `TestProfileMottoAndPublicRanks`：测试昵称长度、宣言外链拦截、资料完整度、最高段位与 >180 天过期标记。
   - `TestGameAccountsConstraints`：测试 BattleTag 格式、大小写不敏感全局唯一、上限 5 个、段位更新。
   - `TestContactsConstraints`：测试 QQ/微信/手机号校验、每种类型限一条、删除联系方式。
   - `TestAccountDeletion`：测试注销密码验证、在任队长禁止注销、原地匿名化、自有数据级联清理、会话作废与 Cookie 清除。
   - `TestDeactivationAndReactivation`：测试停用必须填原因、清空会话、重新启用清空原因、注销账号禁止重新启用。
   - `TestExportAccount`：测试个人数据完整导出。
   - `TestAdminUsersVisibilityAndRoles`：测试仅超管可见邮箱、仅 CapContactsView 可见联系方式、角色更新、单人规则配置。
   - `TestImportLegacyAccounts`：测试从模拟 Django SQLite 库导入存量数据并保持 ID 与关系完整。

## 验收输出

1. **测试机整组检查**（运行编号 `20261009-085710-bc6fba5`，日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-085710-bc6fba5.log`，退出码 0）：
   - `gofmt -l .`：干净。
   - `go vet ./...`：通过。
   - `staticcheck ./...`：通过。
   - `govulncheck ./...`：0 个符号级漏洞。
   - `go test ./...`：全部 17 个 Go 包测试通过（账号域全量契约测试全部通过）。
   - `pnpm test`：样式、Vitest、Vite 客户端与 SSR 生产构建全部通过。
   - 首页壳 gzip 体积：73530 字节（脚本上限 122880，合计上限 307200，BUDGET-OK）。
2. **账号域业务契约 R001–R042 逐条自动化验证通过**。
3. **存量 Django SQLite 数据导入演练通过**。
