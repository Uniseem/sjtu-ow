# 240 用户注册与验证码（POST /api/auth/register）

## 背景

M3 账号里程碑第二轮。依据 `docs/rewrite-research/12-architecture.md` 5.4、5.7、5.9 以及业务契约 R001–R005、R010：
1. 注册必填：邮箱、密码、确认密码、昵称（2–16 字）、是否交大（二选一）、同意用户协议、同意跨境存储（R001）。
2. 邮箱验证为强制，6 位数字验证码、15 分钟有效、最多 3 次尝试（R002）。
3. 邮箱全站唯一，防止账号枚举：已注册邮箱发「已注册过」提醒信、页面表现完全一致（R004）。
4. 注册限流按访客 IP，20/分/IP（R005、R006）。
5. 「未满 14 周岁不要注册」仅为协议页文案，注册接口无年龄校验（R010）。

## 本轮范围

### 做什么

1. **限流配置**：在 `server/internal/platform/ratelimit/limits.go` 中增加 `AuthSignup`（`PerIP`, 20 次/分钟），更新 `limits_test.go` 对照测试。
2. **存储层扩展**：在 `server/internal/accounts/store.go` 中增加 `email_codes` 的写入与清理方法（`InsertEmailCode`、`DeleteEmailCodes`、`GetLatestEmailCode`），以及事务内读用户的 `GetByEmailNormTx`。
3. **服务层注册逻辑**：在 `server/internal/accounts/service.go` 中实现 `Register(ctx, input)`：
   - 字段校验：邮箱格式、昵称去首尾空白后长度 2–16 字符（按 unicode rune 计算）、密码非空且与确认密码一致、密码强度校验 `auth.Validate`、是否来自交大必选、两个协议必须同意；校验不过返回统一 422 `api.InvalidFields`。
   - 事务外完成耗时操作：Argon2 密码哈希 `auth.Hash`（避免长时间占事务锁和触发 watchdog 警报）、6 位随机数字验证码生成与 SHA-256 哈希。
   - 写事务 `d.WriteTx`：
     - 若邮箱已注册（`users.email_norm` 已存在），不新建账号、不存验证码，向其邮箱发送已注册提醒信（`mail.Letter`），提交事务并对客户端返回标准成功响应（防枚举）。
     - 若邮箱未注册，插入 `users` 记录（`email_verified_at = nil` 未验证状态），清空旧验证码并插入新哈希至 `email_codes`（15 分钟有效期），向其邮箱发送验证码邮件信件（`outbox.Send` 入队至 `jobs.LaneMail`）。
4. **接口层注册**：在 `server/internal/accounts/api.go` 中注册 `POST /api/auth/register`（门 `api.Public`，限流 `ratelimit.AuthSignup`）。
5. **接口生成物**：通过 `sjtuow apigen` 更新 `web/packages/api/src/gen/index.ts`。
6. **测试与变异**：
   - 在 `service_test.go` 和 `api_test.go` 中编写完整测试用例（覆盖正常注册、密码校验、协议必选、交大单选、昵称字符范围、防枚举发信、限流拦截等）。
   - 编写 `mutate.py` 包含至少 3 处变异，验证测试全部变红后恢复。

### 明确不做什么

1. 验证码提交核验与会话登录（`POST /api/auth/verify-email`、`POST /api/auth/login` 等，留给 241 轮）。
2. 重发验证码接口与找回密码接口（后续轮次）。
3. 前端注册页面 Vue 组件（后续轮次）。
4. 不修改任何全局用户配置文件或现行 Django 业务代码。

## 任务

1. `server/internal/platform/ratelimit/limits.go`：新增 `AuthSignup` 并同步 `limits_test.go`。
2. `server/internal/accounts/store.go`：新增验证码读写及事务读用户方法。
3. `server/internal/accounts/service.go`：实现 `Register`，处理校验、防枚举、密码哈希与发信入队。
4. `server/internal/accounts/api.go`：注册 `POST /api/auth/register`，接入 service。
5. `server/cmd/sjtuow/main.go`：更新服务初始化时的 siteURL 传递。
6. 运行 `apigen` 更新 `web/packages/api/src/gen/index.ts`。
7. 测试编写：`service_test.go`、`api_test.go`。
8. 运行测试机远程整组检查与变异测试。

## 验收标准

1. `bash scripts/remote-check.sh` 全绿（Go 测试全过、govulncheck 零漏洞、生成物无 diff、web 测试与体积预算通过）。
2. 变异测试 `mutate.py` 变异点全部被测试捕获（变红后恢复）。
