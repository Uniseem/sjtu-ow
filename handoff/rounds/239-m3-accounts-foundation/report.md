# 239 实现报告

## 结论

完成。建立了 M3 账号域的数据表结构迁移（`users`、`user_roles`、`feature_role_restrictions`、`feature_user_rules`、`email_codes`、`email_changes`）、角色与能力映射、`can_use` 与派生角色规则（R011–R013）、会话解析真实的 `*app.Viewer` 以及 `GET /api/session` 真实接口实现，并同步更新了 `apigen` 生成的前端调用类型。

## 逐条结果

1. **数据库迁移**。`server/db/migrations/00008_accounts.sql`：
   - `users`：id（自增）、email、email_norm（唯一索引）、password_hash、nickname、is_sjtu、agreed_terms_at、agreed_cross_border_at、email_verified_at、password_changed_at、version、is_active、is_superuser、deactivation_note、motto、show_rank、created_at、updated_at，STRICT 模式。
   - `user_roles`：存储 4 个管理角色，级联删除。
   - `feature_role_restrictions`：角色级功能禁用表。
   - `feature_user_rules`：单用户功能规则，级联删除，denied 标记。
   - `email_codes` 与 `email_changes`：验证码哈希与换邮箱中间态。
2. **角色模型与业务规则**。`server/internal/accounts/roles.go`：
   - 4 个存储角色（`content_editor`、`certified_author`、`tournament_admin`、`scrim_admin`）。
   - 3 个派生角色（`sjtu_user`、`external_user`、`contributor`）。
   - 7 个 Feature（`team_create`、`team_apply`、`tournament_register`、`scrim_signup`、`article_submit`、`article_comment`、`avatar_upload`）。
   - 15 个 Cap（能力），角色到能力映射矩阵与设计第 4 章逐格钉住。
   - `CanUse` 判定顺序（规则 11/12）：未登录/停用 → 拒；超管 → 全开；单人规则优先；任一所在角色（含派生角色）受限 → 拒；默认全开；未知 feature 报错。
   - `RunsAdmin`：`is_active && (is_superuser || has CapAdminEnter)`。
3. **数据读写与服务层**。`store.go` 与 `service.go`：
   - `BuildViewer(ctx, userID)` 从数据库提取用户基础信息、分配角色、单人规则和角色限制，自动计算派生角色与 Cap 集合，组装标准 `*app.Viewer`。
4. **接口与生成物**。`api.go` 与 `apigen.go`：
   - 真实实现 `GET /api/session`：访客输出 `{"user": null}`；登录成员输出包含 id、nickname、email、admin、email_verified、is_sjtu 的对象，与 `web/apps/site` 前台完全对齐。
   - `apigen` 增强支持指针结构体生成 `| null` 及字段分号，`runApigen` 重新生成 `web/packages/api/src/gen/index.ts`。
5. **接线**。`server/cmd/sjtuow/main.go`：
   - `viewerOf` 接入真实 `accounts.Service.BuildViewer`。
   - `serve` 挂上 `accounts.NewModule(acctSvc).Routes(reg)`。

## 验收输出

测试机整组检查（日志 `20261008-212124-02e2a14.log`，退出码 0）：

govulncheck：

```
=== Symbol Results ===

No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

Go 测试与生成物一致性检查：

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/accounts	0.015s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/api	0.045s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/apigen	0.006s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.792s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/db	7.748s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/health	0.030s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/jobs	0.037s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/outbox	0.031s
ok  	github.com/Uniseem/sjtu-ow/server/internal/serve	0.010s
```

Web 端检查与体积预算：

```
 Test Files  2 passed (2)
      Tests  12 passed (12)
...
 Test Files  5 passed (5)
      Tests  35 passed (35)
...
首页壳 gzip：HTML 2508 + CSS 17870 + JS 53152 = 73530 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK

== 全部通过 (13:21:58)
```

Chromium 端到端浏览器验证（日志 `20261008-212232-43f21eb.log`，退出码 0）：

```
site ssr on :4278 (api http://127.0.0.1:4759, built assets)

BROWSER-CHECK-OK
```

变异测试（日志 `20261008-212205-2bb07fe.log`，退出码 0）：

```
== 基线 ==
基线绿
  变异 A 停用用户也能使用功能 被测试抓到了（退出码 1）
  变异 B 单用户规则不覆盖角色限制 被测试抓到了（退出码 1）
  变异 C 未验证邮箱也能成为投稿者 被测试抓到了（退出码 1）
  变异 D 拥有 CapAdminEnter 不算进后台 被测试抓到了（退出码 1）
  变异 E 访客 GET /api/session 返回非空对象 被测试抓到了（退出码 1）

全部 5 处变异均被测试抓到
```

## 设计偏差

无。完全遵循 `docs/rewrite-research/12-architecture.md` 5.7/5.8/7 及 `docs/design.md` 4.2/4.3 规划。

## 改动文件

- `server/db/migrations/00008_accounts.sql`：新增账号域基础表迁移
- `server/internal/accounts/roles.go`：角色、能力、功能、CanUse、DerivedRoles、RunsAdmin
- `server/internal/accounts/model.go`：User 模型与 NormalizeEmail
- `server/internal/accounts/store.go`：数据库读写层
- `server/internal/accounts/service.go`：业务服务层与 BuildViewer
- `server/internal/accounts/api.go`：GET /api/session 路由与处理函数
- `server/internal/accounts/roles_test.go`：角色矩阵与 CanUse 规则测试
- `server/internal/accounts/service_test.go`：Store 与 BuildViewer 数据库集成测试
- `server/internal/accounts/api_test.go`：/api/session 接口测试
- `server/internal/platform/apigen/apigen.go`：支持指针生成 TypeScript `| null` 与字段分号
- `server/cmd/sjtuow/main.go`：接入账号服务与真实 viewerOf
- `web/packages/api/src/gen/index.ts`：更新生成的 TS 类型与 getApiSession 调用函数
- `handoff/rounds/239-m3-accounts-foundation/request.md`：本轮要求
- `handoff/rounds/239-m3-accounts-foundation/report.md`：本轮报告
- `handoff/rounds/239-m3-accounts-foundation/mutate.py`：变异测试脚本
