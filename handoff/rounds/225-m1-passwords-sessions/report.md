# 225 实现报告

## 结论

完成。旧的 Argon2、PBKDF2 能验，新写的哈希是 Django 6 的 Argon2 格式；会话表和 `ow_session` 定下来了。5 处变异全部变红后恢复。

## 逐条结果

### 1. 密码哈希

- 认 `argon2$argon2id$v=19$m=…,t=…,p=…$盐$哈希`（raw std base64）和 `pbkdf2_sha256$轮数$盐$std base64`。`!` 开头是不可用密码，验不过。
- 新写的用 time=2、memory=102400、parallelism=8、32 字节、16 字节盐。PBKDF2 验过之后 `upgrade=true`。Argon2 参数比现在的旧（或更耗）也标升级；memory > 102400、time > 4、threads > 8 直接当坏哈希，不拿去算。
- 同时最多 2 个 Argon2，多的排队。认不出、不可用、空密码仍然跑一遍 Argon2。
- 校验：至少 8 个字符、不能全是数字、常见密码表（Django 6 那份，19640 行，嵌进二进制）、和邮箱或昵称的 `quick_ratio` ≥ 0.7。提示是 Django 中文那四句。

对照：PBKDF2 一条 iter=1、一条 Django 默认 1_200_000，和 Python `hashlib.pbkdf2_hmac` 打出来的一致。Argon2 一条盐是 `0..15` 的固定字节，和 `argon2-cffi` 的 `hash_secret` 一致，Go 验过且 `upgrade=false`。

直接依赖 `golang.org/x/crypto v0.55.0`（BSD-3-Clause）。goose 3.28 已经要求这一版，没有把 goose 降到 3.27。

### 2. 会话

`sessions` 表。32 字节令牌，Cookie 值是 base64url，库里是 SHA-256 的十六进制。`ow_session`，HttpOnly，SameSite=Lax，Path=/，14 天；`Secure` 由调用方在生产打开。没有、坏了、过期都是 `(nil, nil)`。改密码 `DeleteOthers` 留着当前这条；停用或注销 `DeleteAll`。`reauth_at` 起 5 分钟内算刚输过密码。最后访问不到一小时不写。全 `server/` 里只有 `session.go` 出现 `INSERT INTO sessions`。登录接口是唯一调用方，等 M3 有了 `/api/auth/login` 再钉。

## 验收输出

全部在测试机上跑。

整组（密码和会话的代码，还没有签名那一轮）。日志 `20261008-174911-4593eb3`，退出码 0。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.703s
GO-OK
2163 条测试分成 4 片
分片 1：541 passed in 81.52s (0:01:21)
分片 2：541 passed in 79.76s (0:01:19)
分片 3：541 passed in 73.30s (0:01:13)
分片 4：540 passed in 67.05s (0:01:07)
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	(cached)
== 生产配置
System check identified no issues (0 silenced).
== Docker 镜像
构建成功：c3ea742fb136
== 全部通过
```

变异（`mutate.py`，基线先绿）。日志 `20261008-175447-c7a9eda`。这一趟后面还带着下一轮的签名代码一起跑整组，变异本身在 `MUTATIONS-OK` 处已经结束。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/auth	0.647s
五处变异全部变红后恢复
MUTATIONS-OK
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 不可用密码也能登录 | 去掉「`!` 开头不算可用」 | `TestUnusablePasswordNeverMatches`：不可用密码应以 ! 开头，后面还跟着随机串 |
| B PBKDF2 验过不升级 | `return ok, ok, nil` 改成 `upgrade=false` | 应验过并要求升级：`upgrade=false` |
| C 库里存令牌原文 | 插入时存 hex 原文，不存 SHA-256 | 应找到用户 7：`<nil>` |
| D 改密码把当前会话也删了 | `<>` 改成 `=` | 当前这条应还在 |
| E 不再查和邮箱昵称像不像 | 相似度判断前加 `false &&` | 和邮箱一样：`[]` |

## 设计偏差

没有。5.7 写的格式、14 天、5 分钟、每小时最多碰一次最后访问，都按那个做。

## 未完成 / 顺带发现

- 注册、登录、验证码是 M3。现在没有用户表，也没有 `/api/auth/login`。
- 常见密码表是 19640 行，不是整 2 万。测试要求不少于 19000，并且含 `password` 和 `123456`。

## 改动文件

- `server/internal/platform/auth/`（`password.go`、`validate.go`、`session.go`、`cookie.go`、测试、`common-passwords.txt.gz`）
- `server/db/migrations/00004_sessions.sql`
- `server/go.mod`、`server/go.sum`
- `THIRD_PARTY_NOTICES.md`（常见密码表，BSD-3-Clause）
- `handoff/rounds/225-m1-passwords-sessions/`
- `handoff/STATUS.md`
