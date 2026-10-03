# 150 后台待办列出没发出去的邮件（报告）

## 做了什么

1. `core/admin_todo.py`：`MAIL_LOOKBACK`（7 天）、`_attempt()`（从任务参数里读第几次尝试）、`mail_failures()`；`_site_rows()` 有放弃的邮件时加一行
2. 设计 v6.43（14.1）
3. `core/tests/test_admin_functions.py` 加 2 条（直接造任务记录）

## 命令输出

变异（测试机，5 处，第一次全部被抓到）：

```
baseline green, 1 tests
caught retries still coming count too -> test_the_owner_hears_about_mail_that_never_went_out
caught old failures count too -> test_the_owner_hears_about_mail_that_never_went_out
caught sent mail counts too -> test_the_owner_hears_about_mail_that_never_went_out
caught no error shown -> test_the_owner_hears_about_mail_that_never_went_out
caught no line at all -> test_the_owner_hears_about_mail_that_never_went_out
restored and green; missed: none
```

整组检查（测试机）：

```
1578 条测试分成 4 片
分片 1：395 passed in 37.16s
分片 2：395 passed in 36.34s
分片 3：394 passed in 36.72s
分片 4：394 passed in 32.53s
...
== Docker 镜像 (23:08:06)
构建成功：e1859db1ec6c
== 全部通过 (23:08:06)
```

演示站升级后（没配 SMTP），超级管理员的待办里会有这一行：

```
(5, 'core.mail.SMTPNotConfigured: 后台尚未配置 SMTP，无法发信。请在「设置 → 全站设置」中填写 SMTP 服务器和发件地址。')
```

## 没做 / 未验证

- 只算任务表里还在的记录：完成的任务记录 30 天后由 `cleanup_old_data` 删掉，7 天的窗口不受影响
- 没有给站长发邮件提醒（邮件本身就坏了）
