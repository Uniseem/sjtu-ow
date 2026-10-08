# 228 实现报告

## 结论

完成。信纸、SMTP 发送、待发信都在。4 处变异全部变红后恢复。

## 逐条结果

### 1. 信纸

纯文本的顺序和现行站 `text_of` 一样：称呼、结论、事实、验证码、条目、段落、按钮、祝好、落款、日期，最后用「——」写为什么收到。HTML 照邮件页头和信纸：交大红、两张头图用 `cid:ow-mark` 和 `cid:ow-horizon`、白卡片、页脚。两张 PNG 嵌进二进制，和 `static/img/email/` 里的字节一致。主题前缀默认 `[SJTU-OW]`，已经以这个前缀开头的不加第二次。按钮下的地址把中文百分号还原成字，`%2F` 留着。

HTML 和 Django 模板不会逐字节相同（`html/template` 的空白、标准库把 `Content-ID` 写成 `Content-Id`）。这轮对的是结构：称呼、验证码、祝好、两张图、没有脚本和外链样式。34 封信的全文对拍是 M7 的事。

### 2. 发送

SMTP 连接和读写默认 20 秒。没配主机报「后台尚未配置 SMTP」。名单非空时，不在名单里的地址跳过，不算失败。一封信一个收件人进 `mail.letter`，失败沿用队列的 1/5/30 分钟。注销邮箱（`.invalid`）和空地址不进收件人。

### 3. 待发信

`held_letters`。`app.Ctx.Letters` 有批次就冻住，同一批、同一封信合并收件人；没有批次就入队。确认时按编号条件更新，只有还是 `waiting` 才改得了，第二次点不再发。查询不再事先滤掉已决定的行，认领只靠这一处条件更新（滤掉的话，把条件更新改坏，测试仍然是绿的）。7 天内才算还在等；操作人已经注销时由系统代发，不再看这 7 天。30 天前的行由 04:00 的清理删掉。

## 验收输出

全部在测试机上跑。变异和整组是同一趟。日志 `20261008-181904-fde21fa`，退出码 0。

```
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/mail	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/outbox	0.011s
四处变异全部变红后恢复
MUTATIONS-OK
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/mail	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/outbox	(cached)
ok  	github.com/Uniseem/sjtu-ow/server/internal/platform/jobs	0.049s
GO-OK
2163 条测试分成 4 片
分片 1：541 passed in 76.57s (0:01:16)
分片 2：541 passed in 72.83s (0:01:12)
分片 3：541 passed in 69.66s (0:01:09)
分片 4：540 passed in 64.35s (0:01:04)
== 迁移
No changes detected
== Go（新栈）
No vulnerabilities found.
Your code is affected by 0 vulnerabilities.
== Docker 镜像
构建成功：0917a13f4919
== 全部通过
```

| 变异 | 改动 | 结果 |
|---|---|---|
| A 落款不再是祝好 | `add(Closing)` 改成 `add("此致")` | 正文里出现「此致」 |
| B 同一封信不合并收件人 | `if found` 前加 `false &&` | 同一封变成两行，`held=2` |
| C 确认可以认领第二次 | 去掉 `AND state = 'waiting'` | 第二次点又发出去：`1 2` |
| D 不看发信名单 | 名单判断前加 `false &&` | 名单外的地址去连 `127.0.0.1:1`，被拒绝 |

## 设计偏差

HTML 不是和 Django 模板逐字节相同，见上面。全站设置里的 SMTP 表还没有，发送函数收下配置。`serve` / `worker` 这轮按请求没挂上。

## 未完成 / 顺带发现

- 34 种信的构造函数和确认页是后面的里程碑。
- `/healthz`、apigen、`serve` / `worker` 还没做。M1 还差这三样。

## 改动文件

- `server/internal/platform/mail/`
- `server/internal/platform/outbox/`
- `server/internal/app/ctx.go`
- `server/internal/platform/jobs/cleanup.go`
- `server/db/migrations/00006_held_letters.sql`
- `handoff/rounds/228-m1-letters-outbox/`
- `handoff/STATUS.md`
