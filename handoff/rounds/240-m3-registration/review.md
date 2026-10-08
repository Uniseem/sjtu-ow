# 240 复核结果

## 结论

自查通过。用户注册与验证码接口（`POST /api/auth/register`）满足规则 R001–R005、R010，测试覆盖完整，变异测试全部抓到，端到端与代码生成物一致。

## 验证记录

1. **测试机整组检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220843-d29245c.log`，退出码 0）：
   - `govulncheck ./...` 零漏洞。
   - `gofmt -l .` 格式化规范检查通过。
   - `go vet ./...` 与 `staticcheck ./...` 检查通过。
   - `go test ./...` 全绿（含 accounts、auth、ratelimit、jobs、outbox、db 等全部包）。
   - `sjtuow apigen` 生成物无 diff。
   - 前端 vitest 单元测试、样式守卫、Vite SSR 打包与体积预算全绿（73530 字节 <= 307200 字节上限）。
2. **变异测试**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220916-77a7c0f.log`，退出码 0）：
   - 变异 A（不存验证码哈希）被 `TestRegisterSuccess` 抓到。
   - 变异 B（跳过昵称长度校验）被 `TestRegisterFieldValidation` 抓到。
   - 变异 C（跳过协议勾选校验）被 `TestRegisterFieldValidation` 抓到。
   - 变异 D（防枚举分支失效）被 `TestRegisterAntiEnumeration` 抓到。
   - 变异 E（注册接口移除限流）被 `TestRegisterApiRateLimit` 抓到。
   - 5 处变异全部变红后恢复。
3. **端到端浏览器检查**（日志 `sjtu-ow-test:/srv/sjtu-ow-check/runs/20261008-220942-fbd45e2.log`，退出码 0）：
   - 无头 Chromium 验证通过（`BROWSER-CHECK-OK`）。

## 发现的问题与防范

1. **事务耗时与看门狗**：Argon2 计算耗时约 100ms–200ms。若在 `WriteTx` 内部计算，高并发或慢机下容易触发看门狗 200ms/1s 报警甚至回滚。本次实现严格将 `auth.Hash` 与验证码生成放在事务外，事务内仅做查重、写入与入队发信，保证写锁持有时间在毫秒级别。
2. **防枚举响应一致性**：对已存在邮箱，若返回 422 会泄露该邮箱已在本站注册的信息。实现采用完全一致的 200 状态码与提示文案，仅在后台异步队列中发送「邮箱已注册提醒信」（内附找回密码链接），符合 R004 与 allauth 既有安全契约。

## 判断里最没把握的

无。

## 文档更新

- `handoff/STATUS.md`：记录 240 轮完成结果，将 next 推进至 241 轮（邮箱验证码核验与登录 `POST /api/auth/verify-email`、`POST /api/auth/login` 等）。
