# 225 M1 第四轮：Django 兼容的密码哈希 + 会话

## 背景

224 把写请求的两道通用防线（限流、幂等键）接上了。M1 还缺认证底座（12 号文档 5.7）：割接后旧密码要能验，新写的哈希旧站也要能认；会话不搬 Django 的，但格式现在就定下来。注册、登录、验证码那些流程是 M3 的事，本轮只做底座。

## 本轮范围

### 做

1. **密码哈希**（`internal/platform/auth`）：
   - 认两种存量格式：`argon2$argon2id$v=19$m=102400,t=2,p=8$…`（Django 6 的 Argon2PasswordHasher）和 `pbkdf2_sha256$<轮数>$<盐>$<哈希>`；`!` 开头是不可用密码（注销），验不过；
   - 新写的哈希用 Django 的 Argon2 格式和参数（time=2、memory=102400、parallelism=8、32 字节），PBKDF2 验过之后 `upgrade=true`，调用方下次登录再换成 Argon2；
   - Argon2 同时最多 2 个（一次约 100 MB），多的排队，上下文取消就放弃；
   - 校验：至少 8 位、不能是常见密码（Django 那份 2 万条，BSD，嵌进二进制）、不能纯数字、不能和邮箱或昵称太像（`quick_ratio` ≥ 0.7，和 Django 的 UserAttributeSimilarityValidator 同口径）。
2. **会话**（`sessions` 表）：32 字节随机令牌，库里只存 SHA-256；Cookie `ow_session`，`HttpOnly; SameSite=Lax`，生产再加 `Secure`，登录起 14 天；改密码删掉这个人的其他会话、停用或注销删全部；`reauth_at` 记重新认证，5 分钟内算「刚输过密码」；最后访问每小时最多写一次。
3. **结构性守卫**：全 `server/` 里只有会话这一个文件会 `INSERT INTO sessions`。登录接口是唯一调用方这件事等 M3 有了 `/api/auth/login` 再钉（现在还没有用户表，建不了会话的入口）。
4. **对照**：PBKDF2 用 Python `hashlib` 的已知向量；Argon2 用 Django 同参数打出的一条真哈希，Go 验得过。

### 不做

- 注册、登录、验证码、找回、改邮箱这些流程（M3）；`/api/auth/login` 本身；djsign、Fernet、任务队列、发信、healthz、apigen。
- 把 Django 的会话行搬过来（5.7：割接时全员重新登录）。

## 验收标准

`cd server && gofmt -l .` 为空，`go vet`、`staticcheck`、`govulncheck`、`go test ./...` 全绿；测试机整组全绿。直接依赖加上 `golang.org/x/crypto`（BSD-3-Clause；Argon2 和 PBKDF2，标准库没有。goose 3.28 已经要求 v0.55.0，本轮把它从传递依赖改成直接引用）。
