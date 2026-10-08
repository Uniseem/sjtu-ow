# 225 复核结果（自查）

连做的自查（`handoff/README.md`），不能替代独立复核。

## 结论

通过。

## 验证记录

- **Argon2 对照**：盐字节 `0..15`、密码 `Correct-Horse-Battery-1`，和 `argon2-cffi` 打出的整串一致，验过且不要求升级。自己新写的哈希也是 `argon2$argon2id$v=19$m=102400,t=2,p=8$…`，验过。
- **PBKDF2**：iter=1 和 Django 默认 1_200_000 都验过，并且 `upgrade=true`。拆掉升级（变异 B）后 `upgrade=false`。
- **不可用密码**：`!` 开头验不过，`IsUsable` 为假。拆掉这个判断（变异 A）后测试红。
- **校验**：太短、全数字、`password`、和邮箱或昵称相同，各有一句中文。拆掉相似度（变异 E）后「和邮箱一样」不再报错。
- **会话**：创建后按 Cookie 找得到用户；过期、坏令牌是 `(nil, nil)`。库里存的是 SHA-256，拆掉（变异 C）后找不回。改密码留下当前、删掉其余；拆掉（变异 D）后当前也没了。重新认证 5 分钟内算刚输过，过一秒不算。一小时内第二次 `Touch` 不写库。Cookie 有 HttpOnly 和 SameSite=Lax，只有 `secure=true` 才带 Secure。
- **唯一插入点**：`TestOnlySessionFileInserts` 扫 `server/`，`INSERT INTO sessions` 只出现在 `session.go`。
- 对照 12 号文档 5.7：两种存量哈希、新哈希用现在的 Argon2、同时最多 2 个、会话不搬 Django 的、14 天、改密码删其他会话。都在。

## 发现的问题（都已当场修掉）

1. 会话查找写成了 `s.db.Read()`，库上的方法是 `ReadPool()`，编译不过。
2. 昵称相似度用「小明的密码啊」对「小明」，`quick_ratio` 只有 0.5，到不了 0.7。改成密码和昵称都是 `playerone`。
3. `go get golang.org/x/crypto@v0.48.0` 会把 goose 从 3.28.0 降到 3.27.0（3.28 要求 crypto v0.55.0）。改回直接依赖 v0.55.0，goose 仍是 3.28.0。

## 判断里最没把握的

- **「只有登录能建会话」现在钉不住。** 没有用户表，也没有登录接口。结构上只保证全仓库只有 `session.go` 会插入会话行。M3 有了 `/api/auth/login` 再补「别的地址建不了」。
- **Argon2 在测试机上很快。** 整个 auth 包 0.703 秒，含对照哈希和「同时最多 2 个」那条。100 MB 的信号量在这台上没有把测试拖红。
- **变异和整组不在同一次日志里。** 整组是 `20261008-174911-4593eb3`（含镜像 `c3ea742fb136`）。变异是后面一次 `20261008-175447-c7a9eda` 的前半段，基线 `auth 0.647s` 绿，五处都变红后恢复。后半段整组带着下一轮的签名代码，不记在本轮结论里。

## 文档更新

- `handoff/STATUS.md`
- `THIRD_PARTY_NOTICES.md`（常见密码表）
