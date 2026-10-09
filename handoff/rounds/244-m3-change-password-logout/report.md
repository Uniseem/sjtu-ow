# 244 实现报告

## 结论

完成。实现了 M3 第六轮修改密码与退出登录：`POST /api/auth/change-password` 已登录修改密码并作废其他会话、`POST /api/auth/logout` 退出登录作废当前会话并下发清除 Cookie（对应业务契约 R006，以及 12 号架构文档 5.4、5.7、5.9）。

- `POST /api/auth/change-password`：需要登录（Member 门），限流 5 次/分/人（`PerUser`，`ratelimit.AuthChangePassword`，对应 allauth `change_password 5/m/user`）。入参 `old_password`、`password`、`confirm_password`。严格校验当前密码（`auth.Verify`，不正确 422 `api.InvalidFields`）、新密码强度与相似度（`auth.Validate`）、两次输入一致性、以及新密码不能与旧密码相同。事务外计算 Argon2id 哈希避免持锁耗时；事务内原子更新用户密码与 `password_changed_at`，并调用 `s.sessions.DeleteOthersTx` 作废除当前请求携带的会话外的所有其他会话记录。当前会话保持有效，不破坏用户登录态。
- `POST /api/auth/logout`：需要登录（Member 门），写接口声明 `api.NoLimit("退出登录无需限流")`。从数据库物理删除当前会话（`s.sessions.Delete`），并在 HTTP 响应头中下发 `Max-Age: -1` 清除 `ow_session` Cookie（`ctx.ClearSessionCookie()`）。

## 设计变更与修订（先改文档再改代码）

1. **12 号文档 5.7 流程表**：更新「改密码」与「退出」两行规格（详细记录 `POST /api/auth/change-password` Member 门、5/分/人限流、当前密码核验、新密码强度校验、新旧不得相同、事务外 Argon2id、删其他会话保留当前会话；以及 `POST /api/auth/logout` Member 门、删除当前会话、响应管道清除 Cookie、api.NoLimit）。
2. **12 号文档 15 节修订记录**：增加 244 轮记录。

## 逐条结果

1. **限流核心配置**（`server/internal/platform/ratelimit/`）：
   - `limits.go`：新增 `AuthChangePassword`（PerUser 5/分/人，对应 allauth `change_password 5/m/user`）。更新注释待落地清单。
   - `limits_test.go`：更新 `TestTableMatchesDesign` 对照断言表。
2. **平台层扩展**：
   - `server/internal/app/ctx.go`：`app.Ctx` 补充 `SessionToken string`，增加 `clearSessionCookie bool`、`ClearSessionCookie()` 与 `ShouldClearSessionCookie() bool`。
   - `server/internal/platform/api/registry.go`：
     - 请求绑定阶段从 Cookie 提取当前令牌：`ctx.SessionToken = auth.TokenFromRequest(req)`。
     - 响应下发阶段检查 `ctx.ShouldClearSessionCookie()`，若为真则调用 `auth.ClearCookie(w, cfg.secureCookies)`。
   - `server/internal/platform/auth/session.go`：
     - 增加 `DeleteOthersTx(ctx context.Context, tx *db.Tx, userID int64, keepCookie string) error`，供事务内原子删除除保留令牌外的其他会话；`DeleteOthers` 委托调用此方法。
3. **服务层**（`server/internal/accounts/service.go`）：
   - `ChangePassword(ctx *app.Ctx, in ChangePasswordInput) (*ChangePasswordResult, error)`：
     - 登录状态检查（未登录/停用返回 401 `api.Unauthorized`）。
     - 表单校验：`old_password` 必填、`password` 必填、`confirm_password` 必填且一致、新旧密码不可相同（返回 422 `api.InvalidFields`）。
     - 核验旧密码：`auth.Verify` 失败返回 422 `api.InvalidFields{"old_password": ["当前密码不正确。"]}`。
     - 强密码校验：`auth.Validate(in.Password, u.Email, u.Nickname)` 失败返回 422 `api.InvalidFields{"password": pwdErrs}`。
     - 事务外执行 `auth.Hash(in.Password)`（Argon2id）避免持有 SQLite 写锁耗时。
     - 事务内（WriteTx）：原子更新用户密码与 `password_changed_at = now`，并调用 `s.sessions.DeleteOthersTx` 作废该用户的其他会话（保留 `ctx.SessionToken`）。
   - `Logout(ctx *app.Ctx) (*LogoutResult, error)`：
     - 登录状态检查（未登录/停用返回 401 `api.Unauthorized`）。
     - 从数据库删除当前会话：`s.sessions.Delete(ctx.Context, ctx.SessionToken)`。
     - 调用 `ctx.ClearSessionCookie()` 标记响应头清除会话 Cookie。
4. **接口层**（`server/internal/accounts/api.go`）：
   - 定义 `ChangePasswordIn`、`ChangePasswordOut`、`LogoutIn`、`LogoutOut`。
   - 注册 `POST /api/auth/change-password`（`api.Member`，`api.Limit(ratelimit.AuthChangePassword)`）。
   - 注册 `POST /api/auth/logout`（`api.Member`，`api.NoLimit("退出登录无需限流")`）。
5. **前端代码生成**（`web/packages/api/src/gen/index.ts`）：
   - 运行 `sjtuow apigen` 导出 `postApiAuthChangePassword` 与 `postApiAuthLogout` 及其类型定义。
6. **测试与变异测试**：
   - `service_test.go`：
     - `TestChangePasswordValidation`：必填字段、两次密码不一致、新旧密码相同、弱密码等 422 校验。
     - `TestChangePasswordUnauthenticatedOrDisabled`：未登录、nil viewer、停用账号拦截。
     - `TestChangePasswordWrongOldPassword`：旧密码错误 422。
     - `TestChangePasswordSuccess`：密码成功更新、password_changed_at 记录当前时间、当前会话 A 保留、其他会话 B 被作废、他人会话 C 不受影响、新密码可成功登录。
     - `TestLogout`：未登录拦截、退出登录成功物理删除会话行并标记清除 Cookie。
   - `api_test.go`：
     - `TestChangePasswordApi`：Member 门拦截（401）、停用账号拦截（401）、旧密码错误 422、修改成功 200 且不干扰会话 Cookie。
     - `TestChangePasswordApiRateLimit`：5 次/分/人限流 429 与 Retry-After，换人不受影响。
     - `TestLogoutApi`：Member 门拦截（401）、登录调用 200 且响应头 Set-Cookie 包含清除指令（Max-Age: -1），库中会话物理删除。
     - `TestSessionCookieOnlyFromAuthRoutes`：遍历注册表断言仅 login 和 verify-email 发新会话，守卫 change-password 和 logout 两接口。
   - 变异测试（`mutate.py`）：7 处变异全部变红后恢复。

## 设计偏差

无（先改设计再改代码）。

## 验收输出

1. **测试机整组检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-083530-3e0cc45.log`，退出码 0）：
   - `gofmt -l .`：干净。
   - `go vet ./...`：通过。
   - `staticcheck ./...`：通过。
   - `govulncheck ./...`：0 个符号级漏洞。
   - `go test ./...`：全部 17 个包通过。
   - `apigen`：TypeScript 生成物零 diff。
   - `pnpm test`：样式、Vitest、Vite 构建产物与页面路由测试全部通过。
   - 首页壳 gzip 体积：73530 字节（预算上限 307200 字节，BUDGET-OK）。

2. **变异测试**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-083713-cd1dd03.log`，退出码 0）：
   - 全部 7 处变异均被测试抓到：
     - 变异 A 改密码未作废该用户的其他会话（12 号文档 5.7 会话安全）：抓到（红）
     - 变异 B 改密码未记录 password_changed_at 更新时间：抓到（红）
     - 变异 C 改密码绕过旧密码核验（安全防线失效）：抓到（红）
     - 变异 D 改密码允许新密码与旧密码相同：抓到（红）
     - 变异 E 改密码限流数字偏差（R006 5次/分/人）：抓到（红）
     - 变异 F 退出登录未从数据库物理删除当前会话（5.7 会话安全）：抓到（红）
     - 变异 G 退出登录未通知管道清除会话 Cookie（浏览器仍残留有效凭证）：抓到（红）
   - 全部 7 处变异抓到并已恢复代码。

3. **真浏览器端到端检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-083741-b2bd6a0.log`，退出码 0）：
   - 生产 SSR 启动、无头 Chromium 驱动端到端全流程零 CSP 违规通过（`BROWSER-CHECK-OK`）。
