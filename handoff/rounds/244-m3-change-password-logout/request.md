# 244 修改密码与退出登录（POST /api/auth/change-password 与 POST /api/auth/logout）

## 背景

M3 账号里程碑第六轮。前五轮完成了用户权限底座（239）、注册与发码（240）、验证码登录（241）、重发验证码（242）、找回密码（243）。依据 `docs/rewrite-research/12-architecture.md` 5.4、5.7、5.9 及业务契约 R006：

- **改密码**（已登录修改当前密码）：
  - 接口：`POST /api/auth/change-password`，门为 `api.Member`（未登录或停用 401）。
  - 限流：5 次/分/人（`PerUser`，`ratelimit.AuthChangePassword`，规则 R006，allauth `change_password 5/m/user`）。
  - 入参校验：
    - `old_password` 必填；
    - `password` 必填，强密码校验（`auth.Validate`，不低于 8 位、非全数字、非弱密码、不与邮箱或昵称太像）；
    - `confirm_password` 必填，两次输入必须一致；
    - 新密码不能与当前旧密码相同（相同报 422 `api.InvalidFields{"password": ["新密码不能与当前密码相同。"]}`）。
  - 旧密码核验：`auth.Verify` 核验当前密码，错误返回 422 `api.InvalidFields{"old_password": ["当前密码不正确。"]}`。
  - 哈希与事务：事务外执行 `auth.Hash(in.Password)`（Argon2id）避免持锁耗时；事务内原子更新 `users.password_hash`、`password_changed_at = now`、`updated_at = now`。
  - 会话管理（12 号文档 5.7「改密码时删掉这个人的其他会话」）：保留当前会话（`ctx.SessionToken`），作废该用户在 `sessions` 表中的所有其他会话记录。当前会话 Cookie 保持有效，无需重新登录。
- **退出登录**：
  - 接口：`POST /api/auth/logout`，门为 `api.Member`。
  - 限流：写接口声明 `api.NoLimit("退出登录无需限流")`。
  - 会话作废：物理删除当前请求携带的会话（`s.sessions.Delete(ctx, ctx.SessionToken)`）。
  - 清除 Cookie：通知响应管道写入 `Max-Age: -1` 清除浏览器的 `ow_session` Cookie（`ctx.ClearSessionCookie()` 调用 `auth.ClearCookie`）。
  - 响应：返回 `{ "result": "ok", "message": "已退出登录。" }`。

## 本轮范围

### 做什么

1. **文档修订**（`docs/rewrite-research/12-architecture.md`）：
   - 5.7 流程表更新「改密码」与「退出」两行规格。
   - 15 节修订记录增加 244 轮记录。
2. **限流核心配置**（`server/internal/platform/ratelimit/`）：
   - `limits.go`：新增 `AuthChangePassword`（PerUser 5/分/人，对应 allauth `change_password 5/m/user`）。
   - `limits_test.go`：更新 `TestTableMatchesDesign` 对照断言。
3. **平台层扩展**：
   - `server/internal/app/ctx.go`：`app.Ctx` 补充 `SessionToken string`，增加 `ClearSessionCookie()` 与 `ShouldClearSessionCookie() bool`。
   - `server/internal/platform/api/registry.go`：
     - 请求绑定阶段从 Cookie 提取当前令牌：`ctx.SessionToken = auth.TokenFromRequest(req)`。
     - 响应下发阶段检查 `ctx.ShouldClearSessionCookie()`，若为真则调用 `auth.ClearCookie(w, cfg.secureCookies)`。
   - `server/internal/platform/auth/session.go`：
     - 增加 `DeleteOthersTx(ctx context.Context, tx *db.Tx, userID int64, keepCookie string) error`，供事务内原子删除除保留令牌外的其他会话；`DeleteOthers` 委托调用此方法。
4. **服务层**（`server/internal/accounts/service.go`）：
   - 实现 `ChangePassword(ctx *app.Ctx, in ChangePasswordInput) (*ChangePasswordResult, error)`。
   - 实现 `Logout(ctx *app.Ctx) (*LogoutResult, error)`。
5. **接口层**（`server/internal/accounts/api.go`）：
   - 定义 `ChangePasswordIn`、`ChangePasswordOut`、`LogoutIn`、`LogoutOut`。
   - 注册 `POST /api/auth/change-password`（`api.Member`，`api.Limit(ratelimit.AuthChangePassword)`）。
   - 注册 `POST /api/auth/logout`（`api.Member`，`api.NoLimit("退出登录无需限流")`）。
6. **代码生成与前端对齐**：
   - 执行 `go run ./cmd/sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`。
7. **测试与变异**：
   - `service_test.go`：测试未登录拦截、入参错误（必填、新密码弱、两次不一致、新旧相同）、旧密码错误 422、改密码成功更新哈希与时间、删除其他会话保留当前会话、退出登录作废会话与清除 Cookie。
   - `api_test.go`：测试 Member 门拦截（401）、改密码成功与 422 校验、改密码 5次/分/人限流拦截、退出登录 200 且响应头带清除 Cookie。
   - `mutate.py`：至少 7 处关键变异，测试机全部变红后恢复。

### 明确不做什么

1. 改邮箱（需要 5 分钟内重认证窗口与新邮箱收码核验）——后续轮次。
2. 前端改密码与退出登录 UI 组件——后续轮次。
3. 不动现行 Django 站代码，正式站不动。

## 验收标准

1. `bash scripts/remote-check.sh` 整组全绿。
2. 变异测试全部抓到并退出码 0。
3. browser-check 零违规全绿。
