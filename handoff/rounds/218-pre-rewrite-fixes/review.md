# 218 复核结果（自查）

## 结论

通过（自查，不是独立复核）。

## 验证记录

- 整组检查在测试机上全绿（见 report.md）；17 处变异全部被抓到
- **换个角度看 04-1**：不只看新测试。`/wagtail/login/` 和 `/_util/login/` 现在不接受任何登录（POST 也只是 302）；`WAGTAILADMIN_LOGIN_URL`、`WAGTAIL_FRONTEND_LOGIN_URL`、`LOGIN_URL` 三个设置全部指向 `account_login`；全站带 login 的地址守卫按 `resolve()` 判断。`test_garbage_input.py`（全站地址乱填）整组里也是绿的，说明 `next` 乱填不会 500
- **换个角度看 03-1**：对着 217 的复现步骤（撤下 / 密码 / 登录限制三种状态，HTMX 头，七个接口加回复）逐个断言 404 且正文不在响应里；点赞超限、编辑超限两个分支单独测过
- **换个角度看 09-9**：脚本在 macOS（本机，BSD `date -r`）和测试机（Debian，GNU `date -d`）上都跑过同一组测试；POSIX 的 `CST-8` 不依赖服务器的时区数据库，所以服务器没装 `tzdata` 也对

## 发现的问题

必须修：无。

建议修（留给后面）：
- 03-1 的 service 层不查文章状态（见 report.md 未完成 3）
- Wagtail 自带的密码重置地址行为没有逐个验证（见 report.md 未完成 2）

## 判断里最没把握的

- **`next` 用 `request.get_host()`**：生产设置里 `ALLOWED_HOSTS` 限定了域名，请求头里的 Host 不合法时 Django 本来就 400；反向代理带来的 `X-Forwarded-Proto` 在 `Caddyfile.vps` 里是信任的，所以 `require_https=request.is_secure()` 在正式站为真。没有在正式站上点一遍
- **cron 脚本在真 cron 里的行为**：`$AT 3 -- $DC exec …` 靠 cron 用 `sh -c` 展开变量。`DC=` 那一行原来就这样用，`AT=` 是同样写法，但没有在真 cron 上跑过，只在测试里直接调脚本。换正式站 crontab 时先 `sh at-shanghai.sh 3 -- echo` 试一下（README 写了）
- 夏令时那一天（2026-10-25 柏林 03:00 回到 02:00）真实 cron 对「每小时」条目是否多触发一次：不影响正确性（脚本只看北京时间的小时，北京时间的每个小时只有一个真实小时对应）

## 文档更新

`docs/design.md`（v7.21：3.2、5.6、16.5、附录 D）、`README.md`（定时任务两处）、`AGENTS.md`（第二台的定时任务一行、新增「登录入口全站唯一」的坑、目录表加 `docs/rewrite-research/`）、`docs/rewrite-research/12-architecture.md`（D1–D4 拍板结果）、`docs/rewrite-research/README.md`（状态）、`handoff/STATUS.md`。
