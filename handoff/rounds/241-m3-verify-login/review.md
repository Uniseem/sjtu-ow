# 241 复核结果（自查）

## 结论

通过（自查，非独立复核）。9 处变异全部变红后恢复；对照 12 号文档 5.7（含本轮改后的流程表）和规则 R002、R004、R006–R008 逐条核对无漏。自查过程中发现并当场修了三个问题（见「验证记录」第 4 条）。

## 验证记录

1. **对照设计逐条核对**：
   - R002（6 位码 15 分钟、3 次尝试）：`TestVerifyEmailSuccess`（有效期 15 分钟、attempts 从 0）、`TestVerifyEmailAttempts`（三次作废、作废后对的码也不行）、`TestVerifyEmailExpired`；「支持重发」由登录未验证分支覆盖（`TestLoginUnverifiedResendsCode`：删旧码插新码、重发的码能完成验证），独立的重发接口留给后续轮次（request 已声明）。
   - R004（防枚举）：`TestVerifyEmailUnknownEmailSameError`（未知邮箱与错码错误串逐字一致）、`TestLoginWrongPasswordUnified`（密码错与邮箱不存在同文案）；注册侧防枚举是 240 的 `TestRegisterAntiEnumeration`。**注册接口本轮确认不发任何 Cookie**（「半登录」取消后两分支完全同形），`TestSessionCookieOnlyFromAuthRoutes` 从接口层再兜一道。
   - R006（限流数字）：`limits_test.go` 对照表钉住 `AuthLogin` 30/分/IP、`AuthLoginFailedKey` 5 次/300 秒；`TestLoginApiRateLimit`（第 31 次 429）、`TestLoginFailedRateLimitPerAccount`（5 次 401、第 6 次起 429 且正确密码也拒）、`TestVerifyEmailApiRateLimit`（第 11 次 429，自查补的）。`login_failed 10/m/ip` 不建桶的取舍写在 limits.go 注释（两层现有防线覆盖其语义）。
   - R008（会话 14 天 + 验证后提示补全）：`SessionTTL` 是 M1 既有常量（14 天）；成功消息含「补全游戏 ID 和联系方式」（`TestVerifyEmailSuccess` 断言）；「落到个人资料页」的前端跳转属后续前端轮次。
2. **重跑**：整组检查在测试机全绿（日志 `20261009-002744-73925f7`，退出码 0）；变异基线绿后 9 处全红（日志 `20261009-002821-f28f50d`，退出码 0）；browser-check 回归全绿（日志 `20261009-002902-532ed03`，退出码 0）。
3. **生成物一致性**：`index.ts` 从测试机上的 `sjtuow apigen` 输出原样取回（非手写），check.sh 的 `git diff --exit-code` 再验一遍。
4. **自查抓到、当场修掉的几个问题**：
   - 错码的 attempts 递增最初写在「返回错误的事务」里，会跟着回滚——同一个码可以被无限试（真安全问题）。重构为「事务提交计数、错误在外面报」。
   - 登录失败锁第一版是「第 6 次**失败尝试**起 429」，正确密码仍放行——爆破者可以一直试到撞对那一次。被自己的测试 `TestLoginFailedRateLimitPerAccount` 最后一个断言抓住，重做成「先查锁后数」：锁定期内正确密码也 429。
   - apigen 对连字符路径（`verify-email`）生成非法 TS 标识符（`postApiAuthVerify-email`），`export()` 改成连字符分段驼峰并加守卫测试 `TestHyphenPathMakesValidIdentifiers`。
   - 补了 `AuthVerifyEmail` 的接口级限流测试（此前只有数字对照、没有「接口真的挂了这条」的断言——硬规则 7 缺口）。
   - staticcheck S1016：`VerifyEmailIn` 与 `LoginIn` 使用类型转换而非结构体字面量赋值。
   - 限流测试跨分钟翻页抖动：测试机多次 Argon2 耗时下偶发跨越分钟翻页，已为 `api_test.go` 中限流测试注入 `clock.Fixed` 彻底消除抖动。
5. **变异定位**：mutate.py 每处目标串先断言恰好出现 1 次（本机预检 9/9 通过）；D（停用放行）和 I（防枚举文案）都因两处失败分支代码相同而加长定位串。

## 发现的问题

- 建议修（后续轮次）：无阻塞项。顺带发现：`TestLoginApiRateLimit` 和 `TestVerifyEmailApiRateLimit` 每次都要跑几十次 Argon2 烧毁（邮箱不存在的分支），accounts 包测试时长约 4 秒，尚可接受；真变慢时给这两条换 `PASSWORD_HASHERS` 式的快路径（Go 侧可以注入假的烧毁函数）。

## 判断里最没把握的

- `AuthVerifyEmail` 的 10/分/IP 是新拍的数字（allauth 的 `confirm_email 1/10s/key` 是确认链接、语义不同）。码本身 3 次尝试是主防线，这条只挡乱试脚本；如果以后发现正常用户被误伤（同 IP 多人同时注册），调大即可，limits_test 会提醒同步对照。
- 停用账号登录返回 403 并明说「已被停用」：密码已验证正确、身份成立，不算枚举泄露；这个判断基于现行站行为（停用者知道原因更好找管理员），没有独立设计条文背书。

## 文档更新

- `docs/rewrite-research/12-architecture.md`：5.7 流程表三行（注册不发会话、验证凭邮箱+码、登录未验证分支）、「唯一入口」句、15 节修订记录加 241 行。
- `handoff/STATUS.md`：round/next/updated 与轮次表加 241 行。
- `README.md` / `AGENTS.md`：无命令或流程变化，未动。
