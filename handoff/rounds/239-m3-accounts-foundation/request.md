# 239 M3 第一轮：用户与权限底座

## 背景

M2 前端底座已全部完成并验收（样张和旧站并排截图高度与像素对齐，首页壳 gzip 在预算内）。
按重构规划进入 **M3 账号**（12 号文档 11.2，估计 ~14 轮）。
本轮是 M3 第一轮，建立用户与权限的核心底座：
- 数据库表结构迁移（`users`、`user_roles`、`feature_role_restrictions`、`feature_user_rules`、`email_codes`、`email_changes`）
- 角色模型（4 个存储角色、3 个派生角色、后台能力 Caps、功能权限 Features）
- 业务规则 R011–R013（`can_use` 的优先级与文案规则、投稿者派生资格、后台进门条件）
- 会话解析真实的 `*app.Viewer`（带 Superuser、Disabled、EmailVerified、Caps、FeatureDenied）
- 真实实现 `GET /api/session` 接口（与 `web/apps/site/server.ts` 和 `viewer.ts` 对齐）并更新 `apigen`

## 本轮范围

### 做

1. 数据库迁移 `server/db/migrations/00008_accounts.sql`：
   - `users`：id（自增主键）、email、email_norm（规范化小写唯一）、password_hash、nickname、is_sjtu、agreed_terms_at、agreed_cross_border_at、email_verified_at、password_changed_at、version、is_active、is_superuser、deactivation_note、motto、show_rank、created_at、updated_at（STRICT 模式）。
   - `user_roles`：(user_id, role) 复合主键，外键级联删除。
   - `feature_role_restrictions`：(role, feature) 复合主键。
   - `feature_user_rules`：(user_id, feature) 复合主键，外键级联删除，denied 标记。
   - `email_codes`：用于注册/找回/换绑验证码，只存哈希。
   - `email_changes`：换绑邮箱中转状态。
2. `server/internal/accounts/`：
   - `roles.go`：
     - 4 个存储角色：`content_editor`、`certified_author`、`tournament_admin`、`scrim_admin`。
     - 3 个派生角色：`sjtu_user`（看 `is_sjtu`）、`external_user`、`contributor`（启用 + 邮箱已验证 + `can_use(article_submit)`）。
     - 7 个 Feature（设计 4.3.1）：`team_create`、`team_apply`、`tournament_register`、`scrim_signup`、`article_submit`、`article_comment`、`avatar_upload`。
     - 15 个 Cap（能力）：`admin.enter`、`articles.publish_own`、`articles.edit_any`、`articles.edit_author`、`article_categories.manage`、`site_pages.manage`、`images.contribute`、`images.manage`、`tournaments.manage`、`scrims.manage`、`contacts.view`、`comments.moderate`、`moderation.review`、`member_groups.manage`、`activity.view`。
     - 角色能力矩阵（对照设计第 4 章逐格钉住）。
     - `CanUse` 判定逻辑（规则 11/12）：未登录/停用 → 拒；超管全开；单人规则（允许/禁止）优先；角色限制（任一分配或派生角色）→ 拒；默认全开；未知 feature 报错。
     - `RunsAdmin`：`is_active && (is_superuser || has CapAdminEnter)`。
   - `store.go`：用户、角色、规则的数据库读写。
   - `service.go`：`BuildViewer(ctx, userID)` 从数据库组装 `*app.Viewer`。
   - `api.go`：`GET /api/session` 真实实现，访客返回 `{"user": null}`，登录成员返回 `{"user": {"id": ..., "nickname": "...", "admin": ..., "email_verified": ..., "is_sjtu": ...}}`。
3. `cmd/sjtuow/main.go`：
   - 把 `viewerOf` 接入 `accounts.Service.BuildViewer`。
   - 注册 `/api/session` 进 API 注册表。
   - 运行 `sjtuow apigen` 更新 `web/packages/api/src/gen`。
4. 测试与变异验证：
   - 迁移回滚再执行测试。
   - 角色能力对照矩阵测试。
   - `can_use` 规则矩阵测试（R011、R012、R013）。
   - `GET /api/session` 鉴权与访客状态测试。
   - 编写 `mutate.py`，打坏关键守卫确认测试变红后恢复。

### 明确不做

- 注册、找回密码、修改密码、换邮箱的具体 HTTP 流程（后续轮次）。
- 游戏 ID、联系方式、头像（后续轮次）。
- 历史数据导入与对账（M3 最后一轮）。
- 现行站与正式站任何变动。

## 验收标准

1. 测试机上 `remote-check.sh` 整组全绿（Go + Web，包含 `apigen` 生成检查）。
2. `mutate.py` 变异全部被测试抓到。
3. `govulncheck` 无漏洞。
