# 240 实现报告

## 结论

完成。实现了 M3 第二轮用户注册与验证码接口（`POST /api/auth/register`，对应规则 R001–R005、R010），包含字段严格校验、Argon2 密码哈希、6 位安全随机数字验证码生成与 SHA-256 哈希落库（15 分钟有效、最多 3 次尝试）、已注册邮箱发已注册提醒信（响应一致防枚举）、`outbox.Send` 邮件车道发信入队、访客 IP 限流（20/分/IP），并同步更新了 `apigen` 前端生成代码。

## 逐条结果

1. **限流配置**。`server/internal/platform/ratelimit/limits.go`：
   - 增加 `AuthSignup = Decl{Name: "auth_signup", Kind: PerIP, N: 20, Window: time.Minute}`（规则 5/6，allauth: signup 20/m/ip）。
   - 同步更新 `limits_test.go` 中对照表断言。
2. **存储层方法**。`server/internal/accounts/store.go`：
   - `GetByEmailNormTx(ctx, tx, emailNorm)`：事务内按规范化邮箱查用户。
   - `EmailCode` 结构体及 `InsertEmailCode`、`DeleteEmailCodes`、`GetLatestEmailCode`。
3. **注册业务逻辑**。`server/internal/accounts/service.go`：
   - `validateEmail`：校验邮箱格式（包含 `@`、合法域名及点、无首尾空白、长度合法）。
   - 严格字段校验：昵称去除首尾空白后 Unicode 字符长度需在 2–16 字之间；密码强度校验调用 `auth.Validate`；两次密码一致性校验；是否交大 `is_sjtu` 必选；用户协议与跨境存储协议必须明确同意。校验不通过返回 422 `api.InvalidFields`。
   - 事务外计算：Argon2 密码哈希（`auth.Hash`）与 6 位随机数字验证码生成（`crypto/rand` + SHA-256 哈希），避免长事务占用 SQLite 写锁与触发看门狗报警。
   - 事务内写入：
     - 若邮箱已存在，防枚举逻辑生效：不新建用户、不写验证码，生成 `mail.Letter`（主题「这个邮箱已经注册过」，附找回密码链接），调用 `outbox.Send` 入队并提交事务，对客户端返回完全相同的成功响应（R004）。
     - 若邮箱不存在，插入 `users` 记录（`email_verified_at = nil` 未验证状态），清空旧验证码并插入新哈希至 `email_codes`（15 分钟有效，R002），生成「邮箱验证码」信件调用 `outbox.Send` 直入 `jobs.LaneMail`。
4. **接口层注册**。`server/internal/accounts/api.go`：
   - 注册 `POST /api/auth/register`（门 `api.Public`，限流 `ratelimit.AuthSignup`）。
   - 输入参数 `RegisterIn`、输出参数 `RegisterOut`。
5. **服务与生成物更新**。
   - `server/cmd/sjtuow/main.go`：`NewService` 传入真实的 `cfg.SiteURL`。
   - `sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`，导出 `postApiAuthRegister` 及其类型。
6. **测试用例**。
   - `service_test.go`：`TestRegisterSuccess`（成功建用户、哈希校验、验证码记录、邮件任务入队）、`TestRegisterFieldValidation`（覆盖 11 种字段校验场景）、`TestRegisterAntiEnumeration`（已存在邮箱防枚举判定与提醒信入队）。
   - `api_test.go`：`TestRegisterApi`（200 成功与 422 字段报错响应）、`TestRegisterApiRateLimit`（20 次/分正常，第 21 次返回 429 与 Retry-After）。
7. **变异测试**。`mutate.py` 包含 5 处变异，验证测试有效性。

## 验收输出

测试机整组检查（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220843-d29245c.log`，退出码 0）：

govulncheck：

```
=== Symbol Results ===

No vulnerabilities found.

Your code is affected by 0 vulnerabilities.
```

Go 测试与生成物一致性检查：

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/accounts	1.606s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.891s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/ratelimit	0.021s
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

== 全部通过 (14:09:13)
```

Chromium 端到端浏览器验证（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220942-fbd45e2.log`，退出码 0）：

```
site ssr on :4210 (api http://127.0.0.1:4702, built assets)

BROWSER-CHECK-OK
```

变异测试（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220916-77a7c0f.log`，退出码 0）：

```
== 基线 ==
基线绿
  变异 A 不存验证码哈希 被测试抓到了（退出码 1）
  变异 B 跳过昵称长度校验 被测试抓到了（退出码 1）
  变异 C 跳过协议勾选校验 被测试抓到了（退出码 1）
  变异 D 防枚举分支失效 被测试抓到了（退出码 1）
  变异 E 注册接口移除限流 被测试抓到了（退出码 1）

全部 5 处变异均被测试抓到
```

## 设计偏差

无。完全遵循 `docs/rewrite-research/05-business-rules.md` R001–R005、R010 与 `12-architecture.md` 5.4、5.7、5.9 规划。

## 改动文件

- `server/internal/platform/ratelimit/limits.go`
- `server/internal/platform/ratelimit/limits_test.go`
- `server/internal/accounts/store.go`
- `server/internal/accounts/service.go`
- `server/internal/accounts/api.go`
- `server/internal/accounts/service_test.go`
- `server/internal/accounts/api_test.go`
- `server/cmd/sjtuow/main.go`
- `web/packages/api/src/gen/index.ts`
- `handoff/rounds/240-m3-registration/request.md`
- `handoff/rounds/240-m3-registration/mutate.py`
- `handoff/rounds/240-m3-registration/report.md`
