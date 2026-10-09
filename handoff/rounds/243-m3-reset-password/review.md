# 243 复核结果（连做自查）

## 结论

自查通过。完成了 M3 第五轮找回密码流程（`POST /api/auth/reset-password` 发码与 `POST /api/auth/reset-password/confirm` 核验重置密码），业务规则 R003、R004、R006 均严格成立。

## 验证记录

1. **测试机整组检查**（`scripts/remote-check.sh`，运行编号 `20261009-082102-446392c`，退出码 0）：
   - `gofmt -l .`：干净。
   - `go vet ./...`：通过。
   - `staticcheck ./...`：通过。
   - `govulncheck ./...`：0 个符号级漏洞。
   - `go test ./...`：全部 17 个包通过。
   - `apigen`：TypeScript 生成物零 diff。
   - `pnpm test`：样式、Vitest、Vite 构建产物与页面路由测试全部通过。
   - 首页壳 gzip 体积：73530 字节（预算上限 307200 字节，BUDGET-OK）。
2. **测试机变异测试**（运行编号 `20261009-082136-2d839e1`，退出码 0）：
   - 全部 7 处变异均被对应测试抓到并红。
3. **Chromium 端到端浏览器验证**（运行编号 `20261009-082204-dfa8be6`，退出码 0）：
   - 生产 SSR 服务启动、CDP 驱动无头 Chromium 零 CSP 违规通过（`BROWSER-CHECK-OK`）。

## 发现的问题与处置

1. **会话清理的时序与死锁避免**：
   - 架构文档 5.7 明确要求重置密码后作废该用户所有现有会话。在服务层 `ResetPasswordConfirm` 中，更新密码与作废验证码处于写事务 `WriteTx` 内。
   - `auth.Store.DeleteAll` 自身会启动一个独立的 `WriteTx`。如果在已经持有写事务的闭包中直接调用 `s.sessions.DeleteAll`，在 SQLite 写连接池 `MaxOpenConns(1)` 下会发生自死锁。
   - 处置：在当前的 `WriteTx` 内部直接执行 `DELETE FROM sessions WHERE user_id = ?`，既保证了密码更新与会话作废的原子性，又彻底避免了多重写事务死锁。
2. **防账号枚举的一致报错**：
   - 在核验验证码阶段，未知邮箱、已停用账号、过期验证码、错误验证码、尝试次数耗尽，全部统一返回 `errBadCode`（`api.InvalidFields{"code": ["验证码不正确或已过期。"]}`），确保 HTTP 状态码（422）和出参结构完全同形，杜绝调用方推测邮箱注册状态或密码验证进度。
3. **Argon2id 密码哈希耗时与 SQLite 锁保护**：
   - 找回密码重设新密码时，Argon2id 计算需要数十毫秒。如果在 `WriteTx` 内部执行 `auth.Hash`，会不必要地延长 SQLite 写锁占用时间。
   - 处置：在进入 `WriteTx` 之前，先完成表单校验和 `auth.Hash(ctx, in.Password)`，事务内仅执行纯 SQL 写入与会话删除。

## 判断里最没把握的

1. **未注册邮箱找回密码发不发信**：
   - 如果不发信直接静默返回，虽然也可以防枚举，但真实用户如果输错了邮箱或者不记得自己未注册，便无法得知为什么收不到邮件。
   - 依据 12 号架构文档 5.7「没注册的邮箱发『没有注册』的信」以及 Django 现行模板 `unknown_account_message.txt`：入队发送「这个邮箱还没有注册」提醒信，并附带注册链接。前端 HTTP 响应保持统一成功文案，兼顾安全防枚举与真实用户体验。

## 文档更新

- `docs/rewrite-research/12-architecture.md`：
  - 5.7 流程表更新「找回密码」两段接口与限流说明
  - 15 节增加 243 轮修订记录
- `web/packages/api/src/gen/index.ts`：更新生成的 TS client
- `handoff/STATUS.md`：本轮完成后更新
