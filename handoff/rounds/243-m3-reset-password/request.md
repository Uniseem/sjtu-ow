# 243 找回密码（POST /api/auth/reset-password 发 6 位码与 /confirm 核验重置）

## 背景

M3 账号里程碑第五轮。前四轮依次完成了基础表与权限（239）、用户注册与验证码发信（240）、验证码核验与登录（241）、重新发送验证码（242）。当用户遗忘密码时，需要通过邮箱验证码进行密码找回与重置。依据 `docs/rewrite-research/12-architecture.md` 5.4、5.7、5.9 及业务契约 R003、R004、R006：

- 3. 找回密码同样走验证码：3 分钟有效、最多 3 次尝试（R003）。
- 4. 邮箱全站唯一；登录名即邮箱；防止账号枚举（R004）。未注册邮箱发送「这个邮箱还没有注册」提醒信，对客户端返回完全相同成功出参。
- 6. allauth 限流数字：reset_password 20/m/ip + 5/m/key，reset_password_from_key 20/m/ip（R006）。
- 密码强度校验：新密码同样必须满足 `auth.Validate`（至少 8 字、非纯数字、非常见弱密码、不与邮箱过于相似）。
- 会话作废：重置密码成功后删掉该用户的所有现有会话（5.7「改密码时删掉这个人的其他会话」；找回密码未登录，故作废所有现有会话）。
- 不发会话：找回密码流程不发 `ow_session` Cookie（5.7「唯一入口：只有 /api/auth/login 和 /api/auth/verify-email 能建会话」）。

## 本轮范围

### 做什么

1. **文档修订**（`docs/rewrite-research/12-architecture.md`）：
   - 5.7 流程表更新「找回密码」行（详细记录 `POST /api/auth/reset-password` 发 6 位码与 `POST /api/auth/reset-password/confirm` 核验重置流程、防枚举、3 分钟时效、3 次作废、限流与会话清理）。
   - 15 节修订记录增加 243 轮记录。
2. **限流核心配置**（`server/internal/platform/ratelimit/`）：
   - `limits.go`：新增 `AuthResetPassword`（PerIP 20/分）、`AuthResetPasswordKey`（PerKey 5/分/账号，对应 allauth `reset_password 5/m/key`）、`AuthResetPasswordConfirm`（PerIP 20/分，对应 allauth `reset_password_from_key 20/m/ip`）。
   - `limits_test.go`：更新 `TestTableMatchesDesign` 对照断言。
3. **服务层**（`server/internal/accounts/service.go`）：
   - `RequestPasswordReset(ctx, in ResetPasswordInput) (*ResetPasswordResult, error)`：
     - 邮箱格式合法性校验（非法报 422 `api.InvalidFields`）。
     - 查库前先执行账号级限流 `s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResetPasswordKey)`，超限返回 429（杜绝通过限流时间差枚举）。
     - 查库判用户状态：
       - 若用户不存在：事务内入队发「这个邮箱还没有注册」提醒信（附注册链接），返回统一成功消息防枚举。
       - 若用户已停用：不发信，返回统一成功消息防枚举。
       - 若用户正常：事务内作废旧 `password_reset` 验证码、生成 6 位安全随机码与 SHA-256 哈希、插入 `email_codes`（3 分钟有效、attempts 0，R003）、入队发「找回密码验证码」信件，返回统一成功消息。
   - `ResetPasswordConfirm(ctx, in ResetPasswordConfirmInput) (*ResetPasswordConfirmResult, error)`：
     - 表单校验：邮箱有效、6 位数字验证码、密码非空且两次一致、`auth.Validate` 强度校验；失败统一 422 `api.InvalidFields`。
     - 事务外执行 `auth.Hash(in.Password)`（Argon2id），避免持有 SQLite 写锁耗时。
     - 事务内（WriteTx）：
       - 核验用户存在且启用、核验验证码存在且未过期（now > expires_at）、尝试次数未超限（attempts < 3）。
       - 常量时间比对 SHA-256 哈希：不匹配加 attempts（达到 3 次直接物理删除作废），返回 422 `api.InvalidFields{"code": ["验证码无效或已过期"]}`（防枚举统一报错）。
       - 验证码匹配：作废该邮箱的所有 `password_reset` 验证码、更新用户密码哈希与 `password_changed_at`（若 `email_verified_at` 为空则置为当前时间）、删掉该用户的所有现有会话记录。
       - 返回成功出参，不设置任何会话 Cookie。
4. **接口层**（`server/internal/accounts/api.go`）：
   - 定义 `ResetPasswordIn`、`ResetPasswordOut`、`ResetPasswordConfirmIn`、`ResetPasswordConfirmOut`。
   - 注册 `POST /api/auth/reset-password`（`api.Public`，`api.Limit(ratelimit.AuthResetPassword)`）。
   - 注册 `POST /api/auth/reset-password/confirm`（`api.Public`，`api.Limit(ratelimit.AuthResetPasswordConfirm)`）。
5. **代码生成与前端对齐**：
   - 运行 `sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`（生成 `postApiAuthResetPassword` 与 `postApiAuthResetPasswordConfirm`）。
6. **测试与变异**：
   - `service_test.go`：覆盖请求重置未注册发提醒信防枚举、停用账号防枚举、正常账号发 3 分钟码、5次/分账号限流拦截；覆盖确认重置字段校验、弱密码拦截、错码加 attempts、3 次作废、过期作废、成功更新密码与会话作废。
   - `api_test.go`：覆盖接口 HTTP 响应出参不带 Cookie、422 字段报错、429 IP 限流与账号限流；`TestSessionCookieOnlyFromAuthRoutes` 守卫覆盖两接口。
   - `mutate.py`：至少 7 处关键变异，测试机全部变红后恢复。

### 明确不做什么

1. 改邮箱、退出登录（`POST /api/auth/logout`）、改密码（已登录用户修改当前密码）——后续轮次。
2. 前端找回密码页面 Vue 组件——后续轮次。
3. 不动现行 Django 站代码，正式站不动。

## 验收标准

1. `bash scripts/remote-check.sh` 整组全绿。
2. 变异测试全部抓到并退出码 0。
3. browser-check 零违规全绿。
