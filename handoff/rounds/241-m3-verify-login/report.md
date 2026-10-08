# 241 实现报告

## 结论

完成。实现了 M3 第三轮邮箱验证码核验与登录（`POST /api/auth/verify-email`、`POST /api/auth/login`，对应规则 R002、R004、R006–R008），含一处先写进 12 号文档的设计变更（「半登录」会话取消，见「设计变更」）。apigen 顺手修了一个连字符路径生成非法 TS 标识符的缺陷。

## 设计变更（先改文档再改代码）

**「半登录」会话取消**（12 号文档 5.7 流程表改了三行、修订记录加了一行）。原文写「未验证时的会话是『半登录』」，与 240 落地的防枚举冲突：注册接口对「新邮箱」和「已注册邮箱」必须同形响应，若只有新邮箱分支发 `Set-Cookie`，攻击者靠有无该头就能枚举；已注册分支又绝不能发真会话（等于交出账号）。改成：注册成功不发会话；验证页凭「邮箱 + 6 位码」核验（不需要会话），核验通过即登录；登录时密码正确但未验证的发新码并返回 `verify_required`，不发会话。未验证用户就是访客，`Verified`/`Feature`/`Cap` 门自然拒绝。「建会话的唯一入口」从只有 `/api/auth/login` 改成 login 和 verify-email 两个。

## 逐条结果

1. **会话 Cookie 管道**。`app.Ctx` 加 `SetSessionCookie` / `DrainSessionCookies`（令牌不进 JSON）；`api.Registry.Handler` 新增 `WithSecureCookies(bool)`，成功答复前用 `auth.SetCookie` 写 `ow_session`（HttpOnly、SameSite=Lax、14 天，生产带 Secure）。服务层不碰 `http.ResponseWriter`。
2. **限流表**（`ratelimit/limits.go` + 对照测试）：`AuthLogin`（PerIP 30/分，规则 6）、`AuthLoginFailedKey`（PerKey 5 次/300 秒/账号）、`AuthVerifyEmail`（PerIP 10/分，码的 3 次尝试是主防线）。`ratelimit` 加 `PerKey` Kind（key 由服务层拼 `email:` 前缀，注册表层按 IP 兜底）。`Enforcer` 加 `Count`（只读当前时间片计数，供「先查锁」用）。
3. **登录失败锁「先查后数」**：进入时先查该账号失败计数，锁定期内**连正确密码也 429**（不然爆破者可以一直试到撞对的那一次）；密码错（含邮箱不存在）才数一次。第一版是「第 6 次失败起 429」、正确密码放行，被自己的测试 `TestLoginFailedRateLimitPerAccount` 抓住后重做。
4. **存储层**（`store.go`）：`GetLatestEmailCodeTx`（事务内读码，检查与写尝试次数同一事务）、`BumpEmailCodeAttempts`、`DeleteEmailCode`（按 id）、`MarkEmailVerified`、`UpdatePasswordHash`。
5. **`Service.VerifyEmail`**：邮箱+码核验。码不存在/过期/用尽/不匹配/邮箱没注册，一律同一句 422（R004 防枚举）；**错码的尝试计数和用尽删码在事务里提交、错误在外面报**——第一版计数跟着错误回滚，同一个码可以被无限试，自查发现后重构。第 3 次错码作废（R002）。通过：置 `email_verified_at`、删光 signup 码、事务外建会话；成功消息提示补全游戏 ID/联系方式（R008）。验证码生成抽成 `codeGen`（包内可见，测试注入固定码）。
6. **`Service.Login`**：入参 422；先查失败锁；查用户（读池）；`auth.Verify` 验密码（事务外，Argon2 不进事务）；密码错按账号计数 + 统一 401「邮箱或密码不正确」（邮箱不存在同文案、同样烧一遍 Argon2，R004）；停用 403 `account_disabled`（密码已对，可以说明原因）；未验证发新码返回 `verify_required`（不发会话）；PBKDF2 验过在事务里升级 Argon2；建会话返回令牌。
7. **接口层**：两个接口都是 `api.Public`；`verify-email` 限流 `AuthVerifyEmail`、`login` 限流 `AuthLogin`。出参不含令牌。`NewService` 签名加 `sessions`、`limiter`。
8. **apigen 修复**：路径段带连字符（`verify-email`）时生成的 TS 标识符非法（`postApiAuthVerify-email`）；`export()` 改成连字符分段各自大写（→ `postApiAuthVerifyEmail`），加守卫测试 `TestHyphenPathMakesValidIdentifiers`（生成的每个函数/接口名必须是合法 TS 标识符）。
9. **测试**：service 层 10 个新用例（核验成功/三次作废/过期/未知邮箱同文案/字段校验；登录成功/统一文案/按账号失败锁/停用/未验证重发/ PBKDF2 升级/字段校验）；api 层 5 个新用例（核验 200+Cookie 与 422 无 Cookie、Secure 开关、登录三种结果与 422、30 次/分/IP 限流、**唯一建会话入口**——遍历注册表断言除两个 auth 接口外任何答复都不带 `ow_session`）。

## 设计偏差（相对 12 号文档原文）

1. 5.7「半登录」取消——先改了文档（修订记录 241 行），不算未申报偏差。
2. 规则 6 的 `login_failed 10/m/ip` 没有单独建桶：30/分/IP 的总量（AuthLogin）+ 5 次/300 秒/账号（AuthLoginFailedKey）合起来已覆盖其语义，多一条同维度 IP 桶只会让正常用户更早撞墙。取舍写在 `limits.go` 注释里。
3. `AuthVerifyEmail` 的 10/分/IP 是新拍的数字（allauth 的 `confirm_email 1/10s/key` 是确认链接语义，不照搬）；码的 3 次尝试限制（R002）是主防线。

## 验收输出

测试机整组检查（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-002744-73925f7.log`，退出码 0）：

govulncheck：

```
=== Symbol Results ===

No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

Go 测试与生成物一致性检查（17 个包全部通过）：

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/accounts	4.244s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.825s
ok  	github.com/Uniseem/sjtu-ow/server/internal/serve	0.016s
...
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

== 全部通过 (16:28:16)
```

Chromium 端到端浏览器验证（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-002902-532ed03.log`，退出码 0）：

```
site ssr on :4653 (api http://127.0.0.1:4826, built assets)

BROWSER-CHECK-OK
```

变异测试（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-002821-f28f50d.log`，退出码 0）：

```
== 基线 ==
基线绿
  变异 A 核验不比哈希（任何码都过） 被测试抓到了（退出码 1）
  变异 B 3 次用尽不删码 被测试抓到了（退出码 1）
  变异 C 密码错也放行 被测试抓到了（退出码 1）
  变异 D 停用账号放行 被测试抓到了（退出码 1）
  变异 E 未验证也发会话（verify_required 分支失效） 被测试抓到了（退出码 1）
  变异 F PBKDF2 验过不升级 被测试抓到了（退出码 1）
  变异 G 失败锁先查失效（锁定期放行） 被测试抓到了（退出码 1）
  变异 H 会话 Cookie 不写响应头 被测试抓到了（退出码 1）
  变异 I 密码错时文案破功（防枚举） 被测试抓到了（退出码 1）

全部 9 处变异均被测试抓到
```

## 未完成 / 顺带发现

- 重发验证码的独立接口（登录页/验证页的「重新发送」按钮）、找回密码、退出、改密码：后续轮次（request 里明确不做）。
- `mutate.py` 的变异 I 目标串需要唯一——两处失败分支代码相同，用带 `if !ok {` 前缀的长串定位密码错那处。
- `api_test.go` 中限流测试（注册、登录、验证码核验）初始未注入固定时钟，在真实测试机多次 Argon2 运算（>1s）下偶发跨越分钟翻页导致时间片计数重置；已为全部三个限流测试注入 `clock.Fixed` 彻底消除时间片翻页抖动。
- staticcheck 提示 S1016（同构 struct literal 应使用类型转换），已规范为 `VerifyEmailInput(in)` 与 `LoginInput(in)`。

## 改动文件

- `docs/rewrite-research/12-architecture.md`（5.7 流程表、唯一入口句、15 节修订记录）
- `server/internal/app/ctx.go`
- `server/internal/platform/api/registry.go`、`errors.go`
- `server/internal/platform/ratelimit/ratelimit.go`、`limits.go`、`limits_test.go`
- `server/internal/platform/apigen/apigen.go`、`apigen_test.go`
- `server/internal/accounts/store.go`、`service.go`、`api.go`、`service_test.go`、`api_test.go`
- `server/cmd/sjtuow/main.go`
- `web/packages/api/src/gen/index.ts`
- `handoff/rounds/241-m3-verify-login/`（request、mutate、report、review）
