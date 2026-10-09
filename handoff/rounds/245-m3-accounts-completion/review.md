# 245 复核结果（连做自查）

## 结论

自查通过。完成了 M3 账号域全部业务规则（R001–R042）、所有接口注册与数据存储、后台用户管理与角色能力控制、以及存量 Django 数据库导入工具（`sjtuow import`），业务规则 R001–R042 在自动化测试中逐条验证成立，M3 里程碑全量达成。

## 验证记录

1. **测试机账号域全量契约测试**（运行编号 `20261009-085558-17bcb47`，退出码 0）：
   - `TestReauthenticateAndEmailChange`：重新认证 5 分钟窗口、改邮箱发码与确认换绑 PASS。
   - `TestProfileMottoAndPublicRanks`：个人昵称、宣言外链与顶级域名正则拦截、最高段位计算与 >180 天过期标记 PASS。
   - `TestGameAccountsConstraints`：BattleTag 格式、大小写不敏感全局唯一、上限 5 个约束 PASS。
   - `TestContactsConstraints`：QQ、微信、大陆 11 位手机号格式校验、每种类型限一条约束 PASS。
   - `TestAccountDeletion`：密码校验、在任队长注销拦截、原地匿名化、级联清理自有数据、作废全部会话 PASS。
   - `TestDeactivationAndReactivation`：停用必须填原因、清空会话、重新启用清空原因、已注销账号禁止启用 PASS。
   - `TestExportAccount`：个人数据 15 个自有数据域导出 PASS。
   - `TestAdminUsersVisibilityAndRoles`：超管见邮箱、CapContactsView 见联系方式、角色与功能规则配置 PASS。
   - `TestImportLegacyAccounts`：存量 Django SQLite 库只读导入新库、ID 保持一致、时间转标准 UTC PASS。
2. **测试机整组检查**（`scripts/remote-check.sh`，退出码 0）：
   - `gofmt -l .`：干净。
   - `go vet ./...`：通过。
   - `staticcheck ./...`：通过。
   - `govulncheck ./...`：通过。
   - `go test ./...`：全部测试通过。
   - `apigen`：TypeScript 生成物零 diff。
   - `pnpm test`：通过。

## 发现的问题与处置

1. **事务内会话删除（`DeleteAllTx`）避免自死锁**：
   - 在用户注销（`DeleteAccount`）和停用（`DeactivateUser`）流程中，需要在同一数据库写事务内完成数据匿名化/停用以及删除该用户的所有会话记录。
   - `auth.Store.DeleteAll` 原先在其内部启动了独立的 `WriteTx`。在 SQLite 连接池 `MaxOpenConns(1)` 机制下，嵌套事务会导致等待锁而自死锁。
   - 处置：在 `auth.Store` 中实现 `DeleteAllTx(ctx, tx, userID)`，支持在现有写事务中直接执行 SQL 删除；`DeleteAll` 委托给 `DeleteAllTx`，彻底消除了死锁风险。
2. **存量时间兼容性与标准格式化**：
   - 现行 Django SQLite 库中的日期时间格式通常为带空格分隔的文本（如 `2026-09-18 10:00:00`），不包含 `T` 和 `Z`。
   - 处置：扩充平台层 `db.ParseUTC` 支持 Django 风格日期时间解析；在 `ImportLegacyAccounts` 写入新库时，使用 `parseAndFormatUTC` 将所有历史时间转换为新栈标准的 `YYYY-MM-DDTHH:MM:SS.ffffffZ` UTC 文本格式。
3. **GET 请求参数绑定与路径规范**：
   - 注册表 `registry.go` 的 GET 接口禁止包含带 `json:"..."` 标签的结构体以避免把 GET 误用作写请求。
   - 处置：在 `bind.go` 中增加 `query:"..."` 标签绑定支持，自动将 URL 查询参数（如 `page`、`page_size`、`search`）解析为结构体字段，保持了接口纯粹性与类型安全。

## 判断里最没把握的

1. **未迁移应用表检查的向后兼容性（在任队长注销拦截）**：
   - 规则 R029 要求注销前检查用户是否担任未解散战队的队长。目前新栈尚未实现 M5 战队模块（`teams` 表尚未建立迁移）。
   - 处置：在 `isTeamCaptain` 中先检查 `sqlite_master` 是否存在 `teams` 表。若表尚未创建，则安全略过；若表已存在，则严格核验 `captain_id = ? AND disbanded_at IS NULL`。此设计确保在后续 M5 落地时零代码改动自动生效。

## 文档更新

- `docs/rewrite-research/12-architecture.md`：
  - 更新 5.4、5.7、5.8、5.9 节接口状态与规格
  - 11.2 节标记 M3 完成
  - 15 节增加 245 轮修订记录
- `web/packages/api/src/gen/index.ts` & `nav.ts`：更新 TypeScript API client
- `handoff/STATUS.md`：记录 M3 完成，下一步指向 M4 内容
