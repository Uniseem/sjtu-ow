# 241 邮箱验证码核验与登录（POST /api/auth/verify-email、POST /api/auth/login）

## 背景

M3 账号里程碑第三轮。240 已实现注册与验证码发信（`POST /api/auth/register`），新用户带着未验证账号和一条 signup 验证码停在验证页。本轮接上「核验码并登录」和「邮箱+密码登录」。依据 `docs/rewrite-research/12-architecture.md` 5.4、5.7、5.9 及业务契约 R002、R004、R006–R008：

2. 邮箱验证为强制，6 位数字验证码、15 分钟有效、最多 3 次尝试、支持重发（R002）。
4. 邮箱全站唯一；登录名即邮箱；防止账号枚举（R004）。
6. allauth 限流数字：login 30/分/IP、login_failed 10/分/IP + 5/300秒/账号、confirm_email 1/10秒/账号（R006）。
8. 会话 14 天；验证通过即登录，落到个人资料页并提示补全游戏 ID/联系方式（R008）。

### 一个设计变更（先改 12 号文档 5.7，再写代码）

12 号文档 5.7 流程表原写「未验证时的会话是『半登录』」——即注册成功即发会话。这与 240 落地的防枚举（R004）冲突：注册接口对「新邮箱」和「已注册邮箱」必须返回完全同形的响应，若只有新邮箱分支发 `Set-Cookie`，攻击者靠有无该头就能枚举邮箱；已注册分支又绝不能发真会话（等于交出该账号）。本轮把流程改成：

- **注册成功不发会话**；前端带着邮箱去验证页。
- **验证页凭「邮箱 + 6 位码」核验**（`POST /api/auth/verify-email`，不需要会话）；核验通过即登录：置 `email_verified_at`、建会话、发 `ow_session` Cookie。
- **登录未验证账号**（密码正确）：发一条新验证码并返回 `result: "verify_required"`，不发会话；前端转验证页。
- 「半登录」会话从设计里消失：未验证用户就是访客，`Verified`/`Feature`/`Cap` 门自然拒绝，无需例外逻辑。

用户侧体验不变（注册 → 验证页输码 → 已登录）；安全性更好（防枚举严格成立、未验证用户无会话）。

## 本轮范围

### 做什么

1. **12 号文档 5.7**：流程表按上述变更改三行，15 节修订记录加一行。
2. **会话 Cookie 管道**：`app.Ctx` 加 `SetSessionCookie` / `DrainSessionCookies`；`api.Registry` 的 `Handler` 新增 `WithSecureCookies(bool)` 选项，成功答复前把 Cookie 写进响应头（用 `auth.SetCookie`，生产 Secure）。服务层不碰 `http.ResponseWriter`。
3. **限流表**（`ratelimit/limits.go` + `limits_test.go`）：`AuthLogin`（PerIP 30/分）、`AuthLoginFailedKey`（按账号 5 次/300 秒，服务层在密码错时计数）、`AuthVerifyEmail`（PerIP 10/分）。`ratelimit` 加 `PerKey` Kind（注册表层对它按 IP 兜底，服务层自己拼 `email:` 前缀的 key）。login_failed 的 10/分/IP 不单独建桶：30/分/IP 的总量和 5/300秒/账号的定向爆破防线已覆盖其语义，取舍写进 limits.go 注释。
4. **存储层**（`store.go`）：事务内读最新验证码 `GetLatestEmailCodeTx`、按 id 递增尝试次数、按 id 删单条码、`MarkEmailVerified`、`UpdatePasswordHash`。
5. **服务层**（`service.go`）：
   - `VerifyEmail(ctx, email, code)`：邮箱+码核验。码不存在/过期/用尽/不匹配/邮箱没有对应用户，一律同一句 422（防枚举）；错一次 attempts+1，到 3 次删码作废；对了在写事务里置 `email_verified_at`、删光该邮箱 signup 码，事务外建会话，返回令牌。成功消息提示补全游戏 ID 和联系方式（R008）。验证码生成抽成可替换的 `codeGen`（包内可见），测试注入固定码。
   - `Login(ctx, email, password)`：入参校验（422）；查用户（读池）；`auth.Verify` 验密码（事务外，Argon2 不进事务）；密码错→按账号记失败次数（超限 429）+ 统一 401「邮箱或密码不正确」（R004，邮箱不存在同样文案、同样耗时）；停用→403「账号已被停用」；未验证→写事务删旧码发新码+发信，返回 `verify_required` 不发会话；已验证→PBKDF2 验过则在事务里升级成 Argon2（R006 备注、5.7 密码条），建会话返回令牌。
   - `NewService` 签名加 `sessions *auth.Store` 与 `limiter ratelimit.Limiter`（nil 时自建/跳过，测试可控）。
6. **接口层**（`api.go`）：`POST /api/auth/verify-email`（Public，`api.Limit(ratelimit.AuthVerifyEmail)`）、`POST /api/auth/login`（Public，`api.Limit(ratelimit.AuthLogin)`）。出参不包含令牌（令牌只进 HttpOnly Cookie）。
7. **装配**（`main.go`）：`runServe` 传会话存储、限流执行器、`WithSecureCookies(cfg.Prod)`。
8. **生成物**：`sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`（在测试机上生成，取回本机）。
9. **测试**：核验成功/错码/三次作废/过期/未知邮箱同文案；登录成功发 Cookie、错密码统一文案、按账号失败限流 429、停用 403、未验证重发码不发会话、PBKDF2 升级、接口层 422/429/Set-Cookie；限流对照表更新。每条新规则「拆掉就红」。
10. **变异**：`mutate.py` ≥5 处，测试机上全部变红后恢复。

### 明确不做什么

1. 重发验证码的独立接口、找回密码、改邮箱、退出登录（`POST /api/auth/logout`）、改密码——后续轮次。
2. 前端登录/注册/验证页的 Vue 组件——后续轮次。
3. R007 的重新认证流程（`MarkReauth` 原语 M1 已有，改邮箱轮次接）。
4. 不动现行 Django 站任何代码；正式站不动。

## 验收标准

1. `bash scripts/remote-check.sh` 整组全绿（gofmt/vet/staticcheck/govulncheck/go test、apigen 生成物零 diff、pnpm test 与体积预算）。
2. 变异测试全部变红后恢复，日志与退出码留档。
3. browser-check（改了前台壳才必须；本轮预计不改 `web/`，跑一次作回归）。
