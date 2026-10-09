# 242 重新发送邮箱验证码（POST /api/auth/resend-code）

## 背景

M3 账号里程碑第四轮。240 实现了用户注册与验证码发信（`POST /api/auth/register`），241 实现了邮箱验证码核验与登录（`POST /api/auth/verify-email`、`POST /api/auth/login`）。未验证用户停留在验证页，或者登录提示 `verify_required` 前往验证页时，需要能够重新发送验证码。依据 `docs/rewrite-research/12-architecture.md` 5.4、5.7、5.9 及业务契约 R002、R004、R006：

- 2. 邮箱验证为强制，6 位数字验证码、15 分钟有效、最多 3 次尝试、支持重发（R002）。
- 4. 邮箱全站唯一；登录名即邮箱；防止账号枚举（R004）。
- 6. allauth 限流数字：confirm_email 1/10秒/账号（R006）；接口防发信轰炸限流 10/分/IP。

## 本轮范围

### 做什么

1. **文档修订**（`docs/rewrite-research/12-architecture.md`）：
   - 5.7 流程表新增「重发验证码」行（`POST /api/auth/resend-code`，入参 email，防枚举，作废旧码发新码，限流 10/分/IP 与 1/10s/账号，不发会话）。
   - 5.9 时间片说明补充秒级时间片支持（`<1 分钟按秒片（如 10 秒片），≤1 分钟按整分钟...`）。
   - 15 节修订记录增加 242 轮记录。
2. **限流核心扩展**（`server/internal/platform/ratelimit/`）：
   - `ratelimit.go`：`sliceOf` 与 `untilNextSlice` 支持 `window < time.Minute`（使用 `t.Truncate(window)`，生成秒级格式 `20060102T150405`），精准支持 10 秒窗口（`10*time.Second`），解决 `<1 分钟` 以前被当成整分钟导致过早且过长 429 的问题。
   - `limits.go`：新增 `AuthResendEmailCode`（PerIP 10/分）和 `AuthResendEmailCodeKey`（PerKey 1/10秒/账号，对应 allauth `confirm_email 1/10s/key`）。
   - `limits_test.go`：更新 `TestTableMatchesDesign` 对照断言；`TestSliceMatchesWindow` 补充 10 秒片测试。
3. **接口层**（`server/internal/accounts/api.go`）：
   - 入参 `ResendCodeIn{Email string}`，出参 `ResendCodeOut{Email string, Message string}`。
   - 注册 `POST /api/auth/resend-code`，门为 `api.Public`，限流为 `api.Limit(ratelimit.AuthResendEmailCode)`。
4. **服务层**（`server/internal/accounts/service.go`）：
   - `ResendCode(ctx, in ResendCodeInput) (*ResendCodeResult, error)`：
     - 入参邮箱基础校验（非空、有效格式，非法统一报 422 `api.InvalidFields`）。
     - 按账号限流：`s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResendEmailCodeKey)`，超限 429 `api.TooManyRequests(retry)`。此步骤在用户存在性检查之前执行，杜绝基于限流响应的账号枚举。
     - 查询用户（读池）：
       - 若用户不存在（`u == nil`）：返回统一成功响应，不发信、不报错（R004 防枚举）。
       - 若用户已停用（`!u.IsActive`）：返回统一成功响应，不发信、不报错（防枚举）。
       - 若用户已验证过（`u.EmailVerifiedAt != nil`）：写事务入队提示信（告知邮箱已验证过，无需重发，可直接登录），返回统一成功响应（防枚举）。
       - 若用户未验证（`u.EmailVerifiedAt == nil`）：写事务内作废该邮箱现有旧 signup 码（`DeleteEmailCodes`）、生成 6 位安全随机码与 SHA-256 哈希、插入新码（15 分钟有效、attempts 0，R002）、入队发信（outbox `jobs.LaneMail`），返回统一成功响应。
     - 不发会话（不设置 Cookie）。
5. **代码生成与前端对齐**：
   - 运行 `sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`（生成 `postApiAuthResendCode`）。
6. **测试与变异**：
   - `service_test.go`：覆盖入参校验 422、未注册邮箱防枚举、停用账号防枚举、已验证账号发提示信、未验证账号作废旧码发新码落库、同一账号 10 秒限流 429 与翻页放行。
   - `api_test.go`：覆盖 200 出参形状且无会话 Cookie、422 入参错误、429 接口级 IP 限流（10/分/IP）、429 账号级限流（1/10s/账号）。
   - 变异测试 `mutate.py`：至少 5 处关键逻辑变异（如不作废旧码、不查限流、泄露未注册状态、已验证也发验证码等），测试机全部变红后恢复。

### 明确不做什么

1. 找回密码（`POST /api/auth/reset-password` 等）、改邮箱、退出登录（`POST /api/auth/logout`）、改密码——后续轮次。
2. 前端验证页和登录页的 Vue 组件实现——后续轮次。
3. 不动现行 Django 站代码，正式站不动。

## 验收标准

1. `bash scripts/remote-check.sh` 整组全绿。
2. 变异测试全部抓到并退出码 0。
3. browser-check 零违规全绿。
