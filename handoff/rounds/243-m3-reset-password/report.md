# 243 实现报告

## 结论

完成。实现了 M3 第五轮找回密码流程：`POST /api/auth/reset-password` 发送 6 位验证码，以及 `POST /api/auth/reset-password/confirm` 核验验证码并重置密码（对应业务契约 R003、R004、R006，以及 12 号架构文档 5.4、5.7、5.9）。

配置了 3 项限流规则（`AuthResetPassword` 20/分/IP、`AuthResetPasswordKey` 5/分/账号、`AuthResetPasswordConfirm` 20/分/IP）；未注册邮箱发送「这个邮箱还没有注册」提醒信、页面表现完全同形以杜绝账号枚举；验证码 3 分钟有效、最多 3 次尝试（错码加 attempts，3 次作废）；重设密码要求强密码校验与两次一致；事务外执行 Argon2id 哈希；重设密码成功后作废旧验证码、清理该用户的所有现有会话（5.7）；严格不发会话 Cookie（坚守 5.7 唯一入口规则）。

## 设计变更与修订（先改文档再改代码）

1. **12 号文档 5.7 流程表**：更新「找回密码」行（详细记录 `POST /api/auth/reset-password` 发 6 位码与 `POST /api/auth/reset-password/confirm` 核验重置两段接口、防枚举、3 分钟时效、3 次作废、限流与会话清理）。
2. **12 号文档 15 节修订记录**：增加 243 轮记录。

## 逐条结果

1. **限流核心配置**（`server/internal/platform/ratelimit/`）：
   - `limits.go`：新增 `AuthResetPassword`（PerIP 20/分）、`AuthResetPasswordKey`（PerKey 5/分/账号，allauth: `reset_password 5/m/key`）、`AuthResetPasswordConfirm`（PerIP 20/分，allauth: `reset_password_from_key 20/m/ip`）。
   - `limits_test.go`：更新 `TestTableMatchesDesign` 对照断言表。
2. **服务层**（`server/internal/accounts/service.go`）：
   - `RequestPasswordReset(ctx, in ResetPasswordInput) (*ResetPasswordResult, error)`：
     - 邮箱格式合法性校验（非法报 422 `api.InvalidFields`）。
     - 查库前先执行账号级限流 `s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResetPasswordKey)`，超限返回 429（杜绝通过限流时间差枚举）。
     - 查库判用户状态：
       - 若用户不存在：事务内入队发「这个邮箱还没有注册」提醒信（附注册链接），返回统一成功消息防枚举（R004）。
       - 若用户已停用：不发信，返回统一成功消息防枚举。
       - 若用户正常：事务内作废旧 `password_reset` 验证码、生成 6 位安全随机码与 SHA-256 哈希、插入 `email_codes`（3 分钟有效、attempts 0，R003）、入队发「找回密码验证码」信件，返回统一成功消息。
   - `ResetPasswordConfirm(ctx, in ResetPasswordConfirmInput) (*ResetPasswordConfirmResult, error)`：
     - 表单校验：邮箱有效、6 位数字验证码、密码非空且两次一致、`auth.Validate` 强度校验；失败统一 422 `api.InvalidFields`。
     - 事务外执行 `auth.Hash(in.Password)`（Argon2id），避免持有 SQLite 写锁耗时。
     - 事务内（WriteTx）：
       - 核验用户存在且启用、核验验证码存在且未过期（`now < expires_at`）、尝试次数未超限（`attempts < 3`）。
       - 常量时间比对 SHA-256 哈希：不匹配加 attempts（达到 3 次直接物理删除作废），返回 422 `errBadCode`（`api.InvalidFields{"code": ["验证码不正确或已过期。"]}`）。
       - 验证码匹配：作废该邮箱的所有 `password_reset` 验证码、更新用户密码哈希与 `password_changed_at`（若 `email_verified_at` 为空则置为当前时间）、删掉该用户的所有现有会话记录。
       - 返回成功出参，不设置任何会话 Cookie。
3. **接口层**（`server/internal/accounts/api.go`）：
   - 定义 `ResetPasswordIn`、`ResetPasswordOut`、`ResetPasswordConfirmIn`、`ResetPasswordConfirmOut`。
   - 注册 `POST /api/auth/reset-password`（`api.Public`，`api.Limit(ratelimit.AuthResetPassword)`）。
   - 注册 `POST /api/auth/reset-password/confirm`（`api.Public`，`api.Limit(ratelimit.AuthResetPasswordConfirm)`）。
   - 处理器调用服务层，完全不设置 `ow_session` Cookie。
4. **前端代码生成**（`web/packages/api/src/gen/index.ts`）：
   - 运行 `sjtuow apigen` 导出 `postApiAuthResetPassword` 与 `postApiAuthResetPasswordConfirm` 及其类型定义。
5. **测试与变异测试**：
   - `service_test.go`：
     - `TestRequestPasswordResetFieldValidation`：邮箱空或非法 422
     - `TestRequestPasswordResetUnknownEmailAntiEnumeration`：未注册发提醒信且响应一致
     - `TestRequestPasswordResetInactiveAccountAntiEnumeration`：停用账号静默成功
     - `TestRequestPasswordResetActiveUserCodeAndLetter`：3 分钟码有效、重发旧码作废且仅留 1 条有效码、信件入队
     - `TestRequestPasswordResetRateLimitKey`：5 次/分/账号超限 429 与翻页恢复
     - `TestResetPasswordConfirmFieldValidation`：弱密码、两次密码不一致等 422
     - `TestResetPasswordConfirmCodeAttemptsAndExpiry`：错码递增 attempts、3 次作废、超时失效、防枚举统一报错
     - `TestResetPasswordConfirmSuccess`：密码成功更新、原有会话被作废、新密码可成功登录
   - `api_test.go`：
     - `TestResetPasswordApi`：200 响应出参正确且无 Cookie、422 非法邮箱
     - `TestResetPasswordApiRateLimit`：20 次/分/IP 限流 429
     - `TestResetPasswordConfirmApi`：错码 422、成功 200 且绝对不发 Cookie
     - `TestSessionCookieOnlyFromAuthRoutes`：遍历注册表断言仅 login 和 verify-email 发会话，守卫找回密码两接口
   - 变异测试（`mutate.py`）：7 处变异全部变红后恢复。

## 设计偏差

无（先改设计再改代码）。

## 验收输出

1. **测试机整组检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-082102-446392c.log`，退出码 0）：
   - `gofmt -l .`：干净。
   - `go vet ./...`：通过。
   - `staticcheck ./...`：通过。
   - `govulncheck ./...`：0 个符号级漏洞。
   - `go test ./...`：通过（含 accounts、ratelimit、auth、apigen 等全部包）。
   - `apigen`：TypeScript 生成物零 diff。
   - `pnpm test`：样式、Vitest、Vite 构建产物与页面路由测试全部通过。
   - 首页壳 gzip 体积：73530 字节（预算上限 307200 字节，BUDGET-OK）。

2. **变异测试**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-082136-2d839e1.log`，退出码 0）：
   - 全部 7 处变异均被测试抓到：
     - 变异 A 重置验证码有效期非 3 分钟（R003 违背）：抓到（退出码 1）
     - 变异 B 重发找回密码验证码不作废旧码：抓到（退出码 1）
     - 变异 C 未注册邮箱报错泄露账号不存在（R004 防枚举失效）：抓到（退出码 1）
     - 变异 D 找回密码账号级限流失效（R006）：抓到（退出码 1）
     - 变异 E 核验错码不递增 attempts / 3 次不作废（R003）：抓到（退出码 1）
     - 变异 F 确认重置密码成功后未清理该用户现有会话（5.7 会话安全）：抓到（退出码 1）
     - 变异 G reset-password-confirm 偷发会话 Cookie（违反 5.7 唯一入口规则）：抓到（退出码 1）

3. **真浏览器端到端检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-082204-dfa8be6.log`，退出码 0）：
   - 生产 SSR 启动、无头 Chromium 驱动端到端全流程零 CSP 违规通过（`BROWSER-CHECK-OK`）。
