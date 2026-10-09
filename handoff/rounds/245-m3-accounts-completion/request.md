# 245 M3 账号域收尾与全量对齐（完成 R001–R042 与存量导入）

## 背景

M3 账号里程碑终局轮次。在用户「把 M3 一次性做完，少测试，多写代码」的明确要求下，本轮将 M3 账号域的所有剩余业务规则（R001–R042）、所有接口、后台管理能力及存量 Django 数据导入一次性完整交付，完成整个 M3 里程碑。

依据 `docs/rewrite-research/12-architecture.md` 5.7、5.8、5.9、7、8.1 以及 `docs/rewrite-research/05-business-rules.md`：
1. **重新认证与邮箱修改**（规则 R006、R007、R349）：
   - `POST /api/auth/reauthenticate`：5 分钟窗口内重新输入密码，会话记录 `reauth_at`（限流 10次/分/人）。
   - `POST /api/auth/email/change`：必须在 5 分钟重认证窗口内；校验新邮箱有效性与唯一性；向新邮箱发送 6 位验证码（15 分钟有效，试 3 次，限流 10次/分/人）。
   - `POST /api/auth/email/change/confirm`：核验 6 位码；原子更新 `users.email` 与 `email_norm`，作废临时验证码。
2. **个人资料、段位与联系方式**（规则 R016–R021）：
   - `GET /api/me/profile` 与 `PATCH /api/me/profile`：个人昵称（2–16 字）、宣言（≤30 字，正则严禁外链与顶级域名）、主玩位置、补位位置、公开段位开关；自动计算 `is_complete`（至少 1 个游戏 ID + 至少 1 种联系方式）；公开段位为所有游戏 ID 最高分，>180 天标记过期。
   - `POST /api/me/game-accounts`、`PATCH /api/me/game-accounts/{id}`、`DELETE /api/me/game-accounts/{id}`：BattleTag 格式与全局唯一（大小写不敏感），上限 5 个；段位 0–40 整数。
   - `POST /api/me/contacts`、`DELETE /api/me/contacts/{id}`：QQ、微信、中国大陆手机号（11 位 1 开头）、其他（≤64 字符）；每种类型限 1 条。
3. **账号原地匿名化注销**（规则 R028–R032）：
   - `POST /api/auth/delete-account`：必须输入当前密码（限 5次/小时）；在任队长禁止注销；原地匿名化（`email` 改为 `deleted-{id}@deleted.invalid`，昵称改为「已注销用户」，密码置 `!`，清空 roles/is_sjtu/motto，`is_active=false`，`deactivation_note="用户自行注销"`）；级联清理游戏 ID、联系方式、单人规则、角色与待发信；作废全部会话并清除 Cookie。
4. **账号停用与重新启用**（规则 R033–R036）：
   - `POST /api/admin/users/{id}/deactivate`：超管必须填写原因，停用后清空全部会话；
   - `POST /api/admin/users/{id}/activate`：重新启用清空停用原因；禁止启用已注销账号（`@deleted.invalid`）。
5. **个人数据导出**（规则 R037–R038）：
   - `GET /api/me/export`：限 5次/小时，完整导出账号、游戏 ID、联系方式、角色等自有数据域。
6. **后台用户管理与角色功能限制**（规则 R011、R039–R042）：
   - `GET /api/admin/users`：分页搜索用户；仅超管可见邮箱。
   - `GET /api/admin/users/{id}`：用户详情；仅超管及有 `CapContactsView` 者可见联系方式。
   - `PATCH /api/admin/users/{id}/roles`：配置用户角色（内容编辑、赛事管理员、内战管理员、认证作者）。
   - `PATCH /api/admin/users/{id}/rules`：配置单用户功能规则（优先于角色限制）。
   - `GET /api/admin/feature-role-restrictions` 与 `PUT /api/admin/feature-role-restrictions`：配置全站角色功能限制。
7. **数据迁移与服务端命令**（12 号文档 8.1、规则 R015）：
   - `sjtuow import`：从现行 Django SQLite 导入用户、游戏 ID、联系方式、角色、功能限制与规则。
   - `sjtuow verify-email <email>`：服务端直接背书邮箱已验证，不发验证信。

## 本轮范围

### 做什么

1. **数据库迁移**（`server/db/migrations/00009_profile_and_accounts.sql`）：
   - `users` 增加 `main_role`、`flex_roles`；
   - 创建 `game_accounts` 表（`battletag_norm` 全局唯一）；
   - 创建 `contacts` 表（`user_id, type` 唯一约束）；
   - 创建 `email_changes` 表。
2. **限流配置**（`server/internal/platform/ratelimit/limits.go`）：
   - 增加 `AuthReauthenticate`（10/分/人）、`AuthManageEmail`（10/分/人）、`AccountDeleteTry`（5/小时/人）。
3. **平台层扩展**：
   - `server/internal/platform/api/registry.go`：新增 `api.Put`。
   - `server/internal/platform/api/bind.go`：支持 GET 接口的 `query:"..."` 参数绑定。
   - `server/internal/platform/api/errors.go`：`Error()` 输出包含 `Fields` 便于精准诊断。
   - `server/internal/platform/auth/session.go`：新增 `DeleteAllTx`。
4. **服务层与存储层**（`server/internal/accounts/`）：
   - `model.go`：定义 GameAccount、Contact 及联系方式常量。
   - `ranks.go`：段位编解码、格式化、BattleTag/联系方式/宣言/昵称校验、资料完整度与过期段位计算。
   - `store.go`：游戏 ID、联系方式、修改邮箱、注销、停用、用户列表、角色与限制的完整 SQLite 存储层实现。
   - `service.go`：所有账号领域规则与业务逻辑。
   - `api.go`：定义所有 DTO 并注册全部路由（Member、Superuser、CapContactsView 守卫）。
   - `import.go`：实现从 Django 库导入用户的 `ImportLegacyAccounts`。
5. **CLI 工具**（`server/cmd/sjtuow/main.go`）：
   - 增加 `import` 与 `verify-email` 子命令。
6. **前端 SDK**：
   - 运行 `sjtuow apigen` 生成最新 TypeScript 客户端及后台导航。
7. **测试套件**（`m3_full_test.go`）：
   - 覆盖 R001–R042 所有契约规则。

### 明确不做什么

1. M4 内容域（文章、页面、图片、Markdown 对拍等）——下一里程碑。
2. 不动现行 Django 站线上代码。

## 验收标准

1. `bash scripts/remote-check.sh` 整组全绿（Go + Web + TypeScript）。
2. M3 全量业务规则 R001–R042 在测试套件中全部通过。
3. 存量 SQLite 导入测试通过。
