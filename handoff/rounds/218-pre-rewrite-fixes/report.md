# 218 实现报告

## 结论

完成。重写开工前在现行站上要先做的三件事（不含图片管线）修好了：登录入口全站唯一（04-1）、评论接口先查文章是否公开（03-1）、cron 不再受服务器夏令时影响（09-9）。**正式站的 crontab 没动**（要登录服务器，等你点头，见「需要确认」）。

## 逐条结果

| 任务 | 结果 |
|---|---|
| 1 04-1 | `accounts/views.py` 加 `login_door`，`sjtu_ow/urls.py` 把 `wagtail/login/`、`_util/login/` 放在对应 include 之前，设置里加 `WAGTAIL_FRONTEND_LOGIN_URL = "account_login"`。任何方法都 302 到 `/accounts/login/`，`next` 只在是本站地址时带上 |
| 2 03-1 | `comments/views.py` 加 `_comment_and_page`，`reply`、`_moderate`、`_act`、点赞超限、编辑超限五处都经过它，文章没上线或有访问限制一律 404 |
| 3 09-9 | 新增 `deploy/at-shanghai.sh`（`sh at-shanghai.sh 小时 [星期] -- 命令`，用 POSIX 东八区 `CST-8` 算，不依赖时区数据库）；`deploy/crontab.example` 改成「每小时一次 + 脚本判断」，没有 `CRON_TZ`；README 两处、设计 16.5、AGENTS 的定时任务一行跟着改 |

新增测试：

- `accounts/tests/test_single_login_door.py`（12 条）：两个侧门 GET 只跳转；`next` 外链被丢；没验证和已验证的账号 POST 都登不进去（含 8 次错密码）；正门照样要验证邮箱；受限页面和 `/wagtail/` 都跳 allauth；**结构守卫**：全站每个带 login 的地址，按 `resolve()` 看只能由 allauth 或 `login_door` 处理
- `comments/tests/test_comment_page_gate.py`（27 条）：八个接口 × 撤下 / 密码 / 仅登录可见三种状态，都是 404、不渲染评论、评论没被改；点赞和编辑超限分支；一条正常文章的对照
- `core/tests/test_cron_schedule.py`（7 条）：每个北京时间小时只有目标小时执行；星期按北京时间算；**从 10-22 到 10-28 每个真实小时都 tick 一次，恰好每天 03:00（北京）一次，柏林时间那一小时从 21 点变成 20 点**；非法参数拒绝（退出码 64）；命令的退出码保留；`crontab.example` 每一条都和设计 16.5 的表逐条对上

## 验收输出

整组（`bash scripts/remote-check.sh`，测试机，退出码 0）：

```
== ruff   All checks passed! / 431 files already formatted
== pytest 2124 条测试分成 4 片
分片 1：531 passed in 62.49s   分片 2：531 passed in 67.12s
分片 3：531 passed in 66.71s   分片 4：531 passed in 62.18s
== 迁移   No changes detected
== 生产配置 System check identified no issues (0 silenced).
== Docker 镜像 构建成功：8eeab6108d86
== 全部通过
```

变异（`handoff/rounds/218-pre-rewrite-fixes/mutate.py`，测试机）：基线全绿，**17 处变异全部被抓到**，改回后基线全绿。第一遍有一处「没抓到」（`exec "$@"` 改成 `"$@"` 再 `exit 0`）：那不是缺陷，`set -e` 下命令失败照样带着原退出码退出；换成真正的缺陷 `"$@" || exit 0` 后被 `test_the_exit_code_of_the_command_is_kept` 抓到。

第一次在测试机上跑新测试时结构守卫红了一次：Wagtail 自己那两条登录地址仍然注册在地址表里（只是被前面的遮住），守卫原来按「注册了什么」判断。改成用 `resolve()` 看**谁在处理这个地址**，之后绿。

## 设计偏差

无。设计 v7.21：3.2 加「登录入口全站唯一」，5.6 加「文章要上线、公开才有评论接口」，16.5 改 cron 写法，附录 D 记一行。

## 未完成 / 顺带发现 / 需要确认

1. **正式站的 `/etc/cron.d/sjtu-ow` 还是旧的**，2026-10-25 柏林改冬令时之后备份、清理、全量预渲染会整体晚一小时（先后顺序不变，影响不大，但和设计 16.5 不一致）。要在服务器上换成新写法，步骤写在 README「把正式站的 cron 换成新写法」；**要登录正式站改，等你点头**，10-25 之前做
2. 04-1 附带：Wagtail 的 `/wagtail/password_reset/` 等重置密码地址我只核对了地址表（它们还注册着），没有逐个验证行为；`WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False` 应当让它们不可用。写进 219 的顺带核对
3. 03-1 只在视图层挡了，service 层（`toggle_like`、`edit`）本身仍不查文章状态；前台所有入口都经过视图，后台走的是另外的 `backoffice/views/comments.py`。新站（Go）的服务层要自己查，写进新站的规格
4. 03-1 的修法让「内容编辑在前台撤下文章下的评论区里隐藏评论」不可用了（文章不公开时前台根本打不开）；处理走后台「社区 → 评论」，设计 5.6 已写明

## 改动文件

`accounts/views.py`、`sjtu_ow/urls.py`、`sjtu_ow/settings/base.py`、`comments/views.py`、`deploy/at-shanghai.sh`（新）、`deploy/crontab.example`、三份新测试、`docs/design.md`、`README.md`、`AGENTS.md`、`docs/rewrite-research/`（入库，12 号文档记下 D1–D4 的拍板结果）、本轮的 `request.md`、`report.md`、`review.md`、`mutate.py`、`handoff/STATUS.md`。
