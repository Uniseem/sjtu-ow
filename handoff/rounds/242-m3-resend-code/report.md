# 242 实现报告

## 结论

完成。实现了 M3 第四轮重新发送邮箱验证码（`POST /api/auth/resend-code`，对应规则 R002、R004、R006）。扩展了限流时间片算法支持 `<1 分钟` 秒级时间片（`t.Truncate(window)`），精准支持 10 秒窗口（`AuthResendEmailCodeKey`，1/10s/账号）；接口层配置 10/分/IP（`AuthResendEmailCode`）。用户存在性核验前防枚举；未验证账号作废旧码发新码落库；已验证账号发送提示信；停用与未注册账号静默成功。代码生成器更新了前端 API 类型定义。由于 Go 官方漏洞库发布了标准库 net/http 等 9 项漏洞通告（GO-2026-6617 等），本轮顺带将测试机 Go 工具链升级至 **1.26.9**，govulncheck 漏洞数清零。

## 设计变更与修订（先改文档再改代码）

1. **12 号文档 5.7 流程表**：增加「重发验证码」行（`POST /api/auth/resend-code`，入参 email，防枚举，作废旧码发新码，限流 10/分/IP 与 1/10s/账号，不发会话）。
2. **12 号文档 5.9 时间片说明**：增加秒级时间片说明（`<1 分钟按秒片（如 10 秒片），≤1 分钟按整分钟... 秒片用 Truncate(window) 保证 10 秒窗口不会被扩大为 1 分钟`）。
3. **12 号文档 15 节修订记录**：增加 242 轮记录。
4. **AGENTS.md**：更新测试机工具链记录为 1.26.9。

## 逐条结果

1. **秒级时间片与限流核心**（`server/internal/platform/ratelimit/`）：
   - `ratelimit.go`：`sliceOf` 与 `untilNextSlice` 增加 `case window < time.Minute:` 分支，使用 `t.Truncate(window)` 计算窗口边界与秒级格式 `20060102T150405`。
   - `limits.go`：新增 `AuthResendEmailCode`（`Kind: PerIP, N: 10, Window: time.Minute`，防发信轰炸）与 `AuthResendEmailCodeKey`（`Kind: PerKey, N: 1, Window: 10 * time.Second`，对应 allauth `confirm_email 1/10s/key`，R006）。
   - `limits_test.go`：更新对照测试 `TestTableMatchesDesign`，新增 `TestSliceMatchesWindow` 针对 10 秒片的边界与倒计时断言。
2. **服务层**（`server/internal/accounts/service.go`）：
   - 实现 `ResendCode(ctx, in ResendCodeInput) (*ResendCodeResult, error)`。
   - 邮箱输入基础校验（非空、合法格式），非法统一 422 `api.InvalidFields`。
   - 账号级限流 `s.limiter.Allow(ctx, "email:"+emailNorm, ratelimit.AuthResendEmailCodeKey)`，超限返回 429。在数据库查用户前执行，防止利用限流响应进行账号枚举。
   - 用户分支处理：
     - 未注册（`u == nil`）或已停用（`!u.IsActive`）：返回统一成功出参，不发信（R004 防枚举）。
     - 已验证（`u.EmailVerifiedAt != nil`）：写事务内入队提示信告知已验证，无需重发（防枚举）。
     - 未验证（`u.EmailVerifiedAt == nil`）：写事务内作废旧 signup 码（`DeleteEmailCodes`）、生成 6 位安全随机码与 SHA-256 哈希、插入新码（15 分钟有效、attempts 0，R002）、入队发信（outbox `jobs.LaneMail`）。
   - 不生成任何会话 Cookie。
3. **接口层**（`server/internal/accounts/api.go`）：
   - 定义 `ResendCodeIn{Email}` 与 `ResendCodeOut{Email, Message}`。
   - 注册 `POST /api/auth/resend-code`（`api.Public`，限流 `ratelimit.AuthResendEmailCode`）。
   - `resendCode` 处理器调用服务层并返回统一出参。
4. **前端代码生成**（`web/packages/api/src/gen/index.ts`）：
   - 运行 `sjtuow apigen` 导出 `postApiAuthResendCode`、`PostApiAuthResendCodeIn`、`PostApiAuthResendCodeOut`。
5. **测试覆盖**：
   - `service_test.go`：入参校验 422、未注册防枚举、停用账号防枚举、已验证账号发提示信、未验证账号作废旧码发新码并入库验证通过、10 秒账号级限流 429 与翻页放行。
   - `api_test.go`：接口 200 成功且不发会话 Cookie、未注册 200（防枚举）、入参非法 422、10/分/IP 限流 429、跨 IP 同账号 1/10s 限流 429。
   - `TestSessionCookieOnlyFromAuthRoutes`：遍历注册表断言仅 login 和 verify-email 发会话，守卫 resend-code 不偷发会话。
6. **工具链升级**：
   - 测试机 Go 升级到 `go1.26.9.linux-amd64.tar.gz`（SHA-256: `42d158b4d8f7b61ac0a830567c940a86098fb7aac52e467a5ebec03ef5cc2f8d`），更新 `server/go.mod` 为 `go 1.26.9`。

## 设计偏差

无（先改设计再改代码）。

## 验收输出

测试机整组检查（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-080910-71b4404.log`，退出码 0）：

govulncheck（0 漏洞）：

```
=== Symbol Results ===

No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

Go 测试与生成物一致性检查（17 个包全部通过）：

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/accounts	4.391s
ok  	github.com/Uniseem/sjtu-ow/server/internal/app	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/api	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/apigen	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.800s
...
```

Web 端测试与体积预算：

```
 Test Files  2 passed (2)
      Tests  12 passed (12)
...
 Test Files  5 passed (5)
      Tests  35 passed (35)
...
首页壳 gzip：HTML 2508 + CSS 17870 + JS 53152 = 73530 字节（脚本上限 122880，合计上限 307200）
BUDGET-OK

== 全部通过 (00:09:44)
```

Chromium 端到端浏览器验证（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-081015-2a2e29b.log`，退出码 0）：

```
site ssr on :4377 (api http://127.0.0.1:4872, built assets)

BROWSER-CHECK-OK
```

变异测试（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261009-080946-70390db.log`，退出码 0）：

```
== 基线 ==
基线绿
  变异 A 重发不作废旧码 被测试抓到了（退出码 1）
  变异 B 账号级 10 秒限流失效 被测试抓到了（退出码 1）
  变异 C 未注册邮箱报错（防枚举 R004 破功） 被测试抓到了（退出码 1）
  变异 D 已验证账号仍走生成验证码逻辑 被测试抓到了（退出码 1）
  变异 E 停用账号仍发信 被测试抓到了（退出码 1）
  变异 F 秒级时间片退化为分钟片（10秒窗口被扩大为整分钟） 被测试抓到了（退出码 1）
  变异 G resend-code 发出会话 Cookie（破坏唯一建会话入口） 被测试抓到了（退出码 1）

全部 7 处变异均被测试抓到
```

## 未完成 / 顺带发现

- 找回密码（`POST /api/auth/reset-password`）、改邮箱、退出登录（`POST /api/auth/logout`）、改密码：后续轮次。
- 变异 A 抓出了初版测试未断言数据库中旧验证码被完全物理删除的缺陷（只读最新一条导致旧码残存不报错），已在测试中补充断言严格锁死。
- 变异 G 抓出了初版变异脚本中测试函数名不匹配的缺陷，已对齐为 `TestResendCodeApi`。

## 改动文件

- `AGENTS.md`
- `docs/rewrite-research/12-architecture.md`
- `server/go.mod`
- `server/internal/platform/ratelimit/ratelimit.go`
- `server/internal/platform/ratelimit/limits.go`
- `server/internal/platform/ratelimit/limits_test.go`
- `server/internal/accounts/service.go`
- `server/internal/accounts/service_test.go`
- `server/internal/accounts/api.go`
- `server/internal/accounts/api_test.go`
- `web/packages/api/src/gen/index.ts`
- `handoff/rounds/242-m3-resend-code/request.md`
- `handoff/rounds/242-m3-resend-code/mutate.py`
- `handoff/rounds/242-m3-resend-code/report.md`
- `handoff/rounds/242-m3-resend-code/review.md`
