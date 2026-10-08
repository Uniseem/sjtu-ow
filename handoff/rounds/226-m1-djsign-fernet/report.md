# 226 实现报告

## 结论

完成。Django 的 `sign_object` 和 `dumps`（含压缩标记）能验，新签的是同一套；Fernet 用 SHA-256 派生钥匙，空串还是空串。4 处变异全部变红后恢复。

## 逐条结果

### 1. 签名

`internal/platform/djsign`。钥匙是 SHA-256(盐 + `signer` + 密钥)，HMAC-SHA256，URL 安全 base64、不带填充。`SignObject` 不带时间戳，日历用。`Dumps` / `Loads` 在正文后加 base62 时间戳，退订用；前面有 `.` 的正文先 zlib 解开。改一个字符就验不过。黄金值在 `testdata/golden.json`，是 Django 6 用钥匙 `test-secret-key-at-least-32-chars!!` 打的：日历编号 42、编号加版本 `[7, 1]`、退订 `dumps(42)`、一条压过的 `dumps`。

### 2. Fernet

`internal/platform/crypto`。钥匙是 SHA-256(`FIELD_ENCRYPTION_KEY`) 的 32 字节，前一半签名、后一半 AES-128-CBC，和 `core/crypto.py` 交给 cryptography 的那把一样。空串加密、解密都还是空串。解不开返回错误。黄金密文是 `smtp-secret`。没有新依赖。

## 验收输出

全部在测试机上跑。

整组（签名和 Fernet 第一次进检查）。日志 `20261008-175447-c7a9eda`，退出码 0。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/crypto	0.008s
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/djsign	0.007s
GO-OK
2163 条测试分成 4 片
分片 1：541 passed in 75.32s (0:01:15)
分片 2：541 passed in 73.42s (0:01:13)
分片 3：541 passed in 68.57s (0:01:08)
分片 4：540 passed in 65.17s (0:01:05)
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/crypto	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/djsign	(cached)
== 生产配置
System check identified no issues (0 silenced).
== Docker 镜像
构建成功：f1a85a6364bd
== 全部通过
```

变异（`mutate.py`，基线先绿）。日志 `20261008-180215-77fd808`。这一趟后面还带着下一轮的任务队列一起跑整组，变异本身在 `MUTATIONS-OK` 处已经结束。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/djsign	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/crypto	(cached)
四处变异全部变红后恢复
MUTATIONS-OK
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 签名钥匙少了 signer | 派生时去掉字面量 `signer` | 日历串变成 `NDI:fqc7HYRj…`，和 Django 的对不上 |
| B 不认压缩标记 | 只认前缀 `never` | 压缩的那条：`签名对不上` |
| C Fernet 两半钥匙对调 | 签名钥匙和加密钥匙互换 | 得到空串，`密文和当前的 FIELD_ENCRYPTION_KEY 对不上` |
| D 空串也被加密 | 空串判断改成永远碰不上的字面量 | 空串变成一条 `gAAAAA…` 密文 |

## 设计偏差

没有。5.11 写的算法、压缩标记、`SIGNING_KEY` = 旧的 `DJANGO_SECRET_KEY`、Fernet 派生，都按那个做。环境变量这轮没有新的必填项，222 已经要求 `SIGNING_KEY` 和 `FIELD_ENCRYPTION_KEY`。

## 未完成 / 顺带发现

- 日历 feed、退订页面是 M7。这轮只保证签得开、验得过。
- 全站设置的表还没有，密文还没接到 SMTP 密码上。

## 改动文件

- `server/internal/platform/djsign/`
- `server/internal/platform/crypto/`
- `handoff/rounds/226-m1-djsign-fernet/`
- `handoff/STATUS.md`
