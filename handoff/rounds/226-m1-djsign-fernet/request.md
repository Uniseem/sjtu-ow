# 226 M1 第五轮：Django 签名兼容 + Fernet

## 背景

225 把密码和会话的原语立起来了。日历订阅地址和退订链接是用 Django 的 `SECRET_KEY` 签的（12 号文档 5.11）：换栈后验不了，手机上订着的日历会断，发出去的退订链接全部失效。全站设置里的 SMTP 密码、对象存储密钥是 Fernet 密文（`core/crypto.py`：SHA-256 派生钥匙），解不开就迁不过去。

## 本轮范围

### 做

1. **`internal/platform/djsign`**：Django 6 的 `Signer.sign_object` / `unsign_object` 和 `signing.dumps` / `loads`。HMAC-SHA256，钥匙是 SHA-256(盐 + `signer` + 密钥)，URL 安全 base64 不带填充。`dumps` 带时间戳（base62）；前面有 `.` 的是 zlib 压缩，也要认。新签发的地址用同一算法、同一密钥（`SIGNING_KEY` = 现在的 `DJANGO_SECRET_KEY`）。
2. **`internal/platform/crypto`**：Fernet。钥匙是 SHA-256(`FIELD_ENCRYPTION_KEY`) 再做 URL 安全 base64，和 `core/crypto.py` 一致。空串加密解密都还是空串。解不开返回错误，不把明文和密文混着当成功。
3. **黄金用例**：用 Django / cryptography 打出的真值写进测试——日历两种载荷（只有编号、编号加版本）、退订的 `dumps`、一条带压缩标记的 `dumps`、一条 Fernet 密文。Go 解出来和当初签进去的一样；Go 自己签的，再用同一算法验得过。

### 不做

- 日历 feed、退订页面本身（M7）；把密文接到全站设置（还没有那张表）。
- 任务队列、信纸、待发信、healthz、apigen。

## 验收标准

`cd server && gofmt -l .` 为空，`go vet`、`staticcheck`、`govulncheck`、`go test ./...` 全绿；测试机整组全绿。不加新依赖（Fernet 用标准库的 AES 和 HMAC，签名也是标准库）。
