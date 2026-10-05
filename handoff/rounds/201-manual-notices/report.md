# 201 赛事内战的改动手动发信，群发可以重复发、第二封起写明之前发过几次（报告）

## 做了什么

用户 10-05：「赛事和内战也改成类似文章那种要手动点发信才行的。而且全站的发送邮件不要限死只能发一次，但是第二封开始在信件开头注明当前文章或者活动之前已经发过多少次邮件了，这次发送可能是有修改。」

先让子任务把「时间改了」「通知全体成员」和全站「只发一次」的记号列了一遍：

- 「时间改了」只在后台保存赛事、内战时触发（`_save_tournament` / `_save_scrim`），只看开始时间，每次保存都发，没有任何记录
- 「通知全体成员」靠 `Broadcast` 的唯一约束只发一次，`send_waiting` 用 `.get()` 也只认一条；赛事内战的「更多」里按钮一直在，点进去才说发过了，文章的按钮发过就藏起来
- 「要求作者修改」本来就能再发；开赛提醒、内战提醒、队长提醒、AI 巡查提醒、取消通知是自动的，各有自己的「发过了」记号，不该重复

改动：

1. **设计**（先改，v7.5）：8.1、9.1 改时间；10.2 两张表；10.3 第二封起的提示；10.4 通知报名的人、可以再发、发送记录；14.2 两行；`docs/admin.md` 文章和赛事内战几处
2. **保存不再发信**：`tournaments.services.time_changed` / `scrims.services.time_changed` 改成 `note_time_change`：已发布、开始时间变成另一个将来的时间时，重排提醒（照旧），记下 `moved_from`（报名的人原来知道的时间；连改几次只记最早那个，改回原样就清掉），不发信。原来的「时间改了」信和发送函数删了
3. **「通知报名的人」**：`core.services.Kind` 加了 `participants`、`update_letter`、`noun`；赛事用原来的收信人（有效名单里的人和散人池），内战是全部报名者。新信 `update_letter` / `scrim_update_letter`：主题「赛事有更新：…」「内战有更新：…」，时间改过写原来和现在，没改说以活动页面为准，管理员的说明（最多 500 字）放进一段。预览页还是 `announce`，加 `?to=participants`，多一个说明框；发出后清掉 `moved_from`
4. **可以再发**：`Broadcast` 去掉唯一约束，加 `audience`（全体成员 / 报名的人）、`before`（这之前同一场发过几次）、`note`、`moved_from`，按（类型、对象）建索引（迁移 `core/0022`、`tournaments/0013`、`scrims/0003`）。`announcement_problem` 不再说「同一场只发一次」，只拦第二条「上线时通知」；`send_waiting` 逐条认领在等的。赛事内战的「更多」和编辑页写「通知全体成员（发过 N 次）」「通知报名的人（发过 N 次）」（一页一次查询），文章发过以后按钮照样在、写发过几次。预览页写「发过 N 次，上次某时发给 M 人」，并提醒这次信的开头会写明
5. **第二封起的提示**：`Letter.notice`，纯文本在称呼后面、HTML 在正文前一块浅红色（`primary-soft` 底、`on-primary-soft` 字）。内容「关于这场赛事「X」，之前已经发过 N 次邮件，这次可能有修改，请以这封为准。」（文章、内战换说法）。`before` 在建发送记录时记下，worker 发信时照它写。「要求作者修改」数同一条内容之前的发信记录，第二封起写「关于这条战队简介，之前已经发过 N 次修改提醒……」
6. **编辑页提示**：赛事、内战编辑页的「接下来」上面，时间改过还没通知时写「开始时间从 X 改到了 Y，报名的人还不知道。通知报名的人」
7. 操作记录的名字（文章的通知全体成员、两种通知报名的人）、后台手册、发布页「每场只能发一次」的说明、样张信（两封「有更新」、一封第二次的）、截图脚本里的样张地址

## 测试

- `tournaments/tests/test_time_changed.py`、`scrims/tests/test_time_changed.py` 重写：改时间不发信、记下原来的时间、提醒重排；连改几次记最早的、改回原样清掉；没动、第一次填、改到过去、草稿都不记；后台保存不发信、编辑页有提示和链接；通知报名的人：收信人对、信里有原来和现在的时间和说明、第一封没有提示、发完提示消失；散人池也收到、没改时间写「信息有更新」；名单被驳回的赛事没人可通知；草稿内战不能通知；内战从后台保存一路到预览、发信、提示消失
- `core/tests/test_announcements.py`：「只发一次」改成「可以再发」：第二封 `before == 1`、纯文本和 HTML 都在正文前写着提示；预览页写发过几次、按钮能点、列表写「发过 1 次」、有「通知报名的人」；文章发过以后按钮还在、第二封有提示；新加一条：文章没有「通知报名的人」、说明最多 500 字
- `moderation/tests/test_ask_author.py`：第二封修改提醒写着之前发过 1 次
- `backoffice/tests/test_backoffice.py` 两处跟着改（保存时调的函数名；只改了秒不记成改时间）

## 命令输出

测试机整组检查：

```
1838 条测试分成 4 片
分片 1：460 passed in 58.13s
分片 2：460 passed in 58.59s
分片 3：459 passed in 59.75s
分片 4：459 passed in 52.67s

== 迁移 (08:08:20)
No changes detected

== 生产配置 (08:08:22)
System check identified no issues (0 silenced).

== 错误页和模板一致 (08:08:23)

== Docker 镜像 (08:08:25)
构建成功：b1d63ea47b59

== 全部通过 (08:08:25)
```

变异（测试机，`mutate.py`，25 处、34 次检查，全部被抓到）：

```
mutations: 25 not applying: none
baseline green, 14 tests
restored and green; missed: none
/srv/sjtu-ow-check/runs/20261005-160835-2b77f03.log
34
```

（最后一行是日志里 `caught` 的行数。）

浏览器（测试机）：

```
看了 163 个地址，0 处有问题
全部走通
```

```
ok  封面留在文章上
ok  浏览器没有报错
全部走通
```

## 部署（正式站）

有迁移，先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-162111.tar.gz（210.8 MB）
```

`deploy_ship.sh 201`（32 个文件，没有删文件）：

```
 Image sjtu-ow-worker Built 
 Image sjtu-ow-web Built 
  Applying tournaments.0013_manual_notices... OK
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 276 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"}, 
```

部署日志里只看到一行 Applying，另外核了三份迁移都已应用：

```
 [X] 0022_manual_notices
 [X] 0003_manual_notices
 [X] 0013_manual_notices
```

正式站真实数据上只读检查（`/root/smoke201.py`，请求工厂 GET，不发信）。正式站上已经有一场发布了的赛事、一场内战和一条以前发的通知：

```
broadcast once constraint left: False
broadcasts: 1 by audience: ['everyone']
moved_from fields: True True
pages: {'/admin/tournaments/': 200, '/admin/scrims/': 200, '/admin/articles/': 200, '/admin/announce/tournament/1/': 200, '/admin/announce/tournament/1/?to=participants': 200, '/admin/tournaments/edit/1/': 200, '/admin/announce/scrim/1/': 200, '/admin/announce/scrim/1/?to=participants': 200, '/admin/scrims/edit/1/': 200}
```

以前那条通知迁移后是「全体成员」、之前发过 0 次；再发这一场时信的开头会写「之前已经发过 1 次」。

## 没做 / 没验证

- 开赛提醒在开赛前 24 小时内保存时会马上发出（`schedule_reminder` 到点就排队），这是原来就有的；下一轮改成自动保存时要处理（调时间的中途不该发提醒）
- `send_waiting` 里「逐条认领」防的是同时触发两次，单线程测试测不出来，没有对应的变异
- 正式站没有配发信，没有真的发出过「有更新」的信
