# 216 实现报告：210 复核剩下的低严重度条目，和四处设计空白

## 结论

完成。210 复核「低」里 211–215 没顺手修掉的条目全部修了（约 40 条，见下表），用户 10-07 交给 Claude 决定的四处设计空白（A2、A12、T7、B11）和日历地址按 Claude 的决定做了（设计 v7.19、v7.20）。修复过程中子代理写测试时又指出三处修复本身的问题（D5 的两个相关漏洞、字体下载走代理时会失败），一并修了。7 个新测试文件 88 个测试函数（加上旧文件里补的几条，整组检查从 215 的 1967 条增加到 2078 条），43 处变异全部被抓到；测试机整组检查 2078 条全绿；三条浏览器旅程走通；镜像改用普通用户的 Compose 演练通过。正式站升级见文末。

## 逐条结果

| 条目 | 改动 | 测试（文件） |
|---|---|---|
| A4 | `accounts/images.py`：`exif_transpose` 挪进 try，EXIF 坏的图提示「读不出」 | 造一个 `Raw profile type exif` 坏掉的 PNG，先证明它让 `exif_transpose` 抛错，再断言 `AvatarError`（`accounts/tests/test_216_account_and_core.py`） |
| A5 | `ACCOUNT_REAUTHENTICATION_REQUIRED = True` | force_login 的人加邮箱被送到重新验证页，邮箱没变（同上） |
| A6 | `me_delete` 每人每小时 5 次 | 5 次错密码后第 6 次用对的密码也被拒、账号还在（同上） |
| A7 | `GameAccount.save` 带 `update_fields` 时把 `ranks_updated_at` 加进去 | 同上 |
| A10 | `over_limit` 放进 `transaction.atomic()`（IMMEDIATE 下串行） | 记录式的确定性测试 + 8 线程真并发计数（同上） |
| A11 | 设计 3.5.1 头像一格改回 v6.73「上传即生效」，`AvatarSubmission` 注释 | 文档 |
| A13 | 补测试：别人的游戏 ID 改、删、自动保存都 404 | 同上 |
| T3 | `_resolve_accounts` 走 `as_id`；`_own_account` 也改走 `as_id`（子代理建议） | `teams/tests/test_216_team_and_registration.py`（服务层和报名页） |
| T4 | `assign_captain` 整个包进事务 | 同上 |
| T5 | `apply_to_team` 进事务并接住 `IntegrityError`；`create_team` 的检查挪进事务 | 同上 |
| T6 | 建队的每日次数只在表单有效时计 | 同上 |
| T8 | `_write_adhoc_roster` 游戏 ID 已删时写空 | 同上 |
| T9 | 两处 `select_for_update` 的注释写明 SQLite 上靠 IMMEDIATE | 注释 |
| 移除队长 | `remove_member` 拒绝移除队长 | 同上 |
| S4 | `players_from` 游戏 ID 已删时写空 | `scrims/tests/test_216_split_edges.py` |
| S5 | 拖到没段位的位置存 0 分；自动保存回服务器存下的两队总分、分差 | 同上 |
| S6 | `teaming.unrated_placements`，生成分队后提示「按 0 分算」 | 同上（真造一个 5v5 角色限定的例子） |
| S8 | `autosave.js` 加 `data-autosave-queue`，分队页两张表单排队存 | 子串守卫（同上） |
| S10 | `can_delete` 用列表已有的 `signup_total` | `assert_no_n_plus_one` 3 对 10（同上） |
| S11 | 设计 12.9.1 补 `roster_changed_at`、`moved_from` | 文档 |
| C7 | `ENCRYPTED_COLUMNS` 补 `moderation_api_key` | 遍历全部模型的 `EncryptedTextField` 和清单比对（账号核心那个文件） |
| C8 | `is_internal` 加 `not is_global`、IPv4 映射地址按 IPv4 判断；字体下载的连接固定连检查过的地址（走代理时检查目标主机、交给标准库建隧道） | 同上 |
| C10 | 镜像以 `app`（uid 10001）运行；Tailwind 命令行核对 sha256（发布页登记的值）；`.dockerignore` 排除 `backups` | 同上和 `core/tests/test_tailwind_cli_fetch.py`；Compose 演练（下面） |
| B4 | `IdChoiceField`（置顶、作者、集合三个选择框都用它） | `backoffice/tests/test_216_backoffice_edges.py` |
| B5 | `autosave.js` 只在框里的值和发出去时一样时才填回服务器的值 | 子串守卫（同上） |
| B7 | 「重新生成」先查路径合不合法 | 同上 |
| B8 | `AutosaveReplayMiddleware` + 每张表单一把 `X-Autosave-Key`；`cleanup_old_data` 删 7 天没动的空草稿 | 同上（同一把钥匙两次只建一篇；清理的保留和删除各几种） |
| B9 | `ArticleForm._update_errors` 把表单里没有的字段的错误挪到整张表单上 | 同上（真造一个撞网址的草稿） |
| B10 | 新文章页的「发布」按钮看栏目上的发布权限 | 同上（只有「添加」权限、没验证邮箱的人） |
| F5 | 选图对话框认出登录页（重定向）和没权限 | 子串守卫（同上） |
| F6 | 头像审核回跳加 `require_https` | 同上 |
| F7 | 选图控件的按钮和整组带字段名 | 同上 |
| F8 | 模板扫描加内联事件、无 `src` 的内联脚本 | `core/tests/test_templates.py` |
| F9 | 头像即选即传先 `flushAll()` 再 `requestSubmit()` | 子串守卫 |
| D5 | `record` 只写到读的那段文字上；**补**：`note_failure` 同样只记到原文字上，巡查只数真写进去的结论 | `moderation/tests/test_216_patrol_edges.py`（含长文巡查中途被改的端到端） |
| D6 | 信里只把本站地址做成链接 | 同上 |
| D7 | 附加请求参数多禁 `functions`、`function_call`、`stream`、`model`，发请求时也去掉 | 同上 |
| D8 | 巡查接住 `http.client.HTTPException` | 同上 |
| D9 | 设计 16 章部署步骤、附录 C 改成 AI 密钥在后台 | 文档 |
| A2 | 只有超管能按邮箱搜人、看到邮箱；其他人「昵称（#编号）」 | `core/tests/test_216_decisions.py`（内容编辑和超管各测） |
| A12 | 停用账号不显示自己的头像 | 同上 |
| T7 | 赛事取消、结束后通过、驳回、编队、解散都拦下 | `tournaments/tests/test_216_closed_tournaments.py`（含审核页） |
| B11 | 通知全体成员 30 分钟内不再发（通知报名的人不限） | `core/tests/test_216_decisions.py`；`test_announcements.py` 里三条连发两次的测试按新规则先把第一封挪到 31 分钟前 |
| 日历 | `User.calendar_version`（迁移 `accounts/0010`），签名带版本号，「换一个订阅地址」 | 同上（没换过的人地址和以前一字不差） |

另外 `core/tests/test_letters.py` 的一条按 D6 设上站点地址（Wagtail 通知信里的链接本来就是本站页面）。

## 验收输出

### 整组检查（测试机，`bash scripts/remote-check.sh`）

```
== ruff (19:04:55)
All checks passed!
== pytest (19:04:57)
分片 1：520 passed in 74.48s (0:01:14)
分片 2：520 passed in 73.13s (0:01:13)
分片 3：519 passed in 72.56s (0:01:12)
分片 4：519 passed in 75.57s (0:01:15)
== 迁移 (19:06:21)
No changes detected
== 生产配置 (19:06:22)
System check identified no issues (0 silenced).
== 错误页和模板一致 (19:06:24)
== Docker 镜像 (19:06:25)
构建成功：73d4de153db8
== 全部通过 (19:06:25)
```

第一次整组检查（加五条决定之前）红了 4 条，都是旧测试按旧设计写的：三条群发测试连发两次撞上 30 分钟冷却，一条邮件测试期望外站地址被做成链接。按新设计改了这 4 条，第二次全绿（上面）。

### 变异（`mutate.py`，测试机）

第一次 43 处里 41 处被抓到，两处没有：

```
!! 移除队长：改坏后测试仍然全绿 —— 没抓到
!! F5 对话框认登录页：改坏后测试仍然全绿 —— 没抓到
```

查明：「移除队长」那行在 `teams/services.py` 里出现两次，变异脚本改到了另一个函数里的那处，测试本身是对的，把变异的原文写长到只命中一处；F5 的测试只查脚本里有没有 `response.redirected` 这个词，而它在错误标记里也出现，改成查完整的判断条件。重跑这两处（`mutate.py 移除队长 F5`，脚本加了按名字筛选）：

```
基线全绿，开始变异。
ok 移除队长：改坏后红了（1 条）
ok F5 对话框认登录页：改坏后红了（1 条）
改回后基线全绿。
```

其余 41 处第一次就是 `ok …：改坏后红了`（原样输出在测试机 `runs/` 里，A4 到「日历换地址不失效」逐行）。子代理写测试时也各自把修复整个退回到改之前的版本跑过一遍，对应的测试都红了（各块的报告里有数字，比如 T7 退回后 `10 failed, 2 passed`）。

### C10：镜像不以 root 运行（`c10_drill.sh`，测试机真 Docker）

```
镜像里的用户：uid=10001(app) gid=999(app) groups=999(app)
== 1. 全新数据卷
ok   migrate
ok   createcachetable + collectstatic
ok   backup 写进 backups 卷
ok   数据库文件归 app
     db.sqlite3 属于 app（10001）
     web 的 1 号进程：/app/.venv/bin/python /app/.venv/bin/gunicorn sjtu_ow.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile - ，uid 10001
     worker 的 1 号进程：python manage.py run_worker ，uid 10001
ok   web 的进程是 10001，不是 root
ok   worker 还在跑、进程是 10001
ok   健康检查脚本（容器里，含 worker 心跳）
== 2. 216 以前的数据卷（属于 root）
     交接前 db.sqlite3 属于 root
ok   不交接直接 migrate（失败了，符合预期：readonly database）
ok   不交接直接往 staticfiles 写文件（失败了，符合预期：Permission denied）
ok   不交接直接往 media 写文件（失败了，符合预期：Permission denied）
ok   不交接直接往 prerendered 写文件（失败了，符合预期：Permission denied）
ok   不交接直接往 backups 写文件（失败了，符合预期：Permission denied）
ok   README 的交接：以 root chown 一次
ok   交接后 migrate
ok   交接后 collectstatic
ok   交接后 backup

C10 演练通过
```

前两次没过，都是演练脚本的问题：第一次 `docker top -eo user,args` 少了 PID 列报错（worker 那项因此「白过」了），改成读容器里 `/proc/1/status`；第二次「旧卷」可以写——查明 **Docker 挂载空的数据卷时会按镜像里挂载点的属主重新设一次**，脚本只把空目录改成 root，一挂上又变回 `app`。正式站的卷里都有文件，不会这样，所以交接是必要的；脚本改成先往每个卷里放一个文件再改属主。

### 浏览器旅程（测试机）

```
=== journey
全部走通
=== journey pages
看了 175 个地址，0 处有问题
全部走通
=== journey admin
ok  新内战打标题就建好（开始时间还空着） /admin/scrims/edit/2/
ok  发布页写着还缺开始时间
ok  补上开始时间就发布了
ok  浏览器没有报错
全部走通
```

## 正式站升级（2026-10-07 03:20 北京时间，补记）

脚本先 `scp` 到服务器再 `bash 脚本 < /dev/null`（215 的坑）：核对要覆盖的 57 个文件和 215 一致 → `backup`（`sjtu-ow-20261007-032024.tar.gz`，210.8 MB）→ 解包、`build` → **先停 `web`、`worker`**（免得交接时旧容器又以 root 写出新文件）→ 用新镜像以 root `chown -R 10001:10001` 五个挂载点 → 迁移（`accounts.0010_user_calendar_version... OK`）→ `up -d` → 全量 `prerender`（成功 12，失败 0）。停机约半分钟，期间 Caddy 回维护页。

```
app /app/data/db.sqlite3
app /app/media
app /app/staticfiles
app /app/prerendered
app /app/backups
web 的 1 号进程 uid：10001
worker 的 1 号进程 uid：10001
迁移干净
{'status': 'ok', 'ok': True, 'checks': {'database': {'ok': True, 'detail': 'ok'}, 'disk': {'ok': True, 'detail': 'free space 26.7%'}, 'worker_heartbeat': {'ok': True, 'detail': 'ok (21s ago)', 'affects_status': True}, 'task_backlog': {'ok': True, 'detail': 'ok', 'affects_status': True}}}
不归 app 的文件：0
backups 可写
```

从本机经域名：`/`、`/news/`、`/members/`、`/accounts/login/`、`/healthz` 都是 200，`/healthz` 对外不带细节，首页带 HSTS。定时任务（`/etc/cron.d/sjtu-ow` 里的 `exec web …`）以后也以 `app` 运行，写的备份归它。

## 设计偏差

无。v7.19（剩下的低）、v7.20（四处设计空白和日历地址）先改文档再改代码；`docs/admin.md` 4.4 跟着改了成员分组的搜人说明。

## 未完成 / 顺带发现

- 子代理指出、这轮**没改**的：信里「本站地址」按 `SITE_URL` 原样比对，将来配成带路径或大小写不同的写法会认不出（现在的配置没问题）；`/wagtail/` 里成员分组的选人框还显示邮箱（只有超管进得去）。
- 20 位编号在 Django 6 上对普通整数主键本来就查不到、不报错（T3 的子代理退回修复时发现），所以 T3 真正修的是「abc」这类非数字；20 位的测试只防退化。
- 210 复核「没来得及看」的几块（`content/legacy_body.py`、头像审核页、评论对未发布文章的接口、`/wagtail/` 旧表单、旧后台页面非自动保存部分、队标解码、字体处理）这轮也没看，留给下一次复核。
- **正式站升级要先交接数据卷**（README「升级到 216」）：先 `build`，再用新镜像以 root `chown -R 10001:10001` 五个挂载点，再迁移、启动。

## 改动文件

见提交的文件列表（业务代码约 45 个文件，测试 7 个新文件和 4 个旧文件，文档 `docs/design.md`、`docs/admin.md`、`README.md`、`handoff/STATUS.md`）。本轮目录：`request.md`、`report.md`、`review.md`、`mutate.py`、`c10_drill.sh`。
