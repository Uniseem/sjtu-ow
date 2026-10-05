# 206 自动保存（下之一）：赛事、内战，和定时任务不重复（报告）

## 做了什么

用户 10-05：「继续做 206」。剩下的拆成两轮：赛事、内战的编辑页和它们排的定时任务是一件事，这一轮做；分队页、队长的战队管理和队标放 207（设计 v7.10）。

1. **赛事、内战编辑页自动保存**（新建、编辑、复制，`backoffice/views/events.py` 的 `_autosave`）：
   - 新建、复制改一处就建成草稿，页面地址换成编辑页，表单底下那句换成「已经建成草稿。填好以后发布」（链到发布页）
   - 必填项空着也存：报名开始和截止时间、内战开始时间在数据库里允许空（迁移 `tournaments/0014`、`scrims/0004`），模型和表单上仍是必填
   - 新建时有问题的字段不存：从「表单动之前的样子」开始（复制的就是照抄来的内容，`core.autosave.new_from_valid_fields`），只写上改了、自己没问题的字段
   - 编辑时照 202 的规则（`save_valid_fields`）；存了东西才记操作记录（30 分钟合并）、记下时间改动、`after_change`
   - 列表里标题空着的写「（未命名赛事）」「（未命名内战）」，没有时间的草稿排在最上面（原来按时间倒序，没时间的会沉到最底下）
   - 「保存」按钮只在没有脚本时出现；「不改了」去掉（自动保存没有可放弃的）
2. **跨字段规则落到一个字段上**：报名截止早于开始拦「报名截止时间」，人数上限小于下限拦「人数上限」，下限小于 1、上限大于 20 也各拦一项。原来这些靠数据库约束，表单报的是整张表单的错，自动保存时四个字段一起不存
3. **发布时才查必填**（`services.missing`）：赛事要标题、报名开始和截止时间（截止晚于开始），内战要标题、开始时间。发布确认页列出还缺什么、按钮不能点、给「去填」的链接；服务里也拦。没填好的草稿不能取消（取消了是公开的，空着的地方会露出来），「更多」里不出「取消」，删掉就行
4. **定时任务不重复排**（`core.tasks.enqueue_once`）：开赛提醒、内战提醒、内战自动结束、报名开始截止时和内战截止开始时的页面刷新，同样的任务（同一个函数、同样的参数）已经排着就不再排。提醒和自动结束到时会重新读活动、没到时间就自己重排，所以排着一个时间不晚于这次要的就够；页面刷新要时间一样才算同一个
5. **提醒时间以内保存的，提醒等 10 分钟**（`core.tasks.reminder_due`）：原来马上发，自动保存以后一边改一边就把半截的内容发出去了。任务到时重新读一遍活动，发的是改完的样子。离开始已经不到 10 分钟的，照旧马上发（晚到的提醒总比没有好）
6. 草稿没有时间时不会出错的几处：赛事的 `phase()`、内战的 `signup_open()`、分队页的复制文字
7. 设计 13.17、8.1、9.1、附录 D；`docs/admin.md` 4.3；README 两处

## 测试

`core/tests/test_autosave_events.py`（10 条）：

- 新赛事只写了简介就建成草稿（标题、两个时间空着，回的 JSON 说了这几项）；列表写「（未命名赛事）」，排在有时间的那项前面；发布页写「还没填好：标题、报名开始时间、报名截止时间」，点了发布还是草稿，服务里直接调也拦；补齐后能发布
- 新内战开始时间空着也建好；发布页写缺开始时间；没填好的草稿取消被拦、编辑页没有「取消」
- 复制时一项有问题：照抄来的人数保留，有问题的那项不存，改了的简介存上
- 报名截止早于开始：只有这一项没存，简介照存
- 已发布的赛事清空标题：不存
- 连续三次自动保存：内战提醒、自动结束各只排了一个
- 页面刷新只在时间一样时算同一个；更早排着的提醒算数、更晚的不算
- 提醒时间以内排提醒：在 10 分钟后；离开始不到 10 分钟：马上；赛事同样，连排两次也只有一个

浏览器走查（干部那一晚）加了三步：新内战打标题就建好、发布页写着还缺开始时间、补上开始时间就发布了。

## 命令输出

（所有检查都在测试机上跑；本机只改文件。）

第一次（新测试写完）：1 条红。

```
FAILED core/tests/test_autosave_events.py::test_a_copy_keeps_what_it_copied_when_a_field_is_wrong
E   assert datetime.datetime(2026, 10, 15, 12, 50, tzinfo=...) == datetime.datetime(2026, 10, 15, 12, 50, 42, 927053, tzinfo=...)
```

测试错了：复制来的时间带秒，浏览器的时间框只到分钟，表单送回的是分钟（`KeepSeconds` 只对已经存在的那一条保留秒，新建的照旧按分钟存，原来整张保存也是这样）。改成按分钟比。同一次有 9 处行太长：在测试机上 `ruff format`，差异拿回本机套上，剩下的手改。

整组检查（最后一次）：

```
== ruff
All checks passed!
== pytest (13:06:06)
1894 条测试分成 4 片
分片 1：474 passed in 57.80s
分片 2：474 passed in 49.94s
分片 3：473 passed in 58.08s
分片 4：473 passed in 53.14s
== 迁移 (13:07:10)
No changes detected
== 生产配置 (13:07:11)
System check identified no issues (0 silenced).
== Docker 镜像 (13:07:14)
构建成功：b88e3be9be74
== 全部通过 (13:07:14)
```

（倒数第二次整组停在 ruff：走查脚本里新加的一行太长；那次 pytest 没跑。）

变异（`mutate.py`，18 处）。写的时候发现计划里有一处改坏了也不会红（把「有错的字段」清空，那个字段照样不在 `cleaned_data` 里，还是不存），换成「表单里标题不再必填」：

```
mutations: 18 not applying: none
baseline green, 10 tests
caught a new tournament waits for its required fields -> test_a_new_tournament_exists_from_its_first_change
caught a new tournament waits for its required fields -> test_a_new_scrim_exists_with_its_start_still_empty
caught a new draft listed last -> test_a_new_tournament_exists_from_its_first_change
caught a tournament published with gaps -> test_a_new_tournament_exists_from_its_first_change
caught the publish page does not say what is missing -> test_a_new_tournament_exists_from_its_first_change
caught a scrim published without a start -> test_a_new_scrim_exists_with_its_start_still_empty
caught a half-filled draft cancelled -> test_a_new_scrim_exists_with_its_start_still_empty
caught a copy starts from blank, not from what it copied -> test_a_copy_keeps_what_it_copied_when_a_field_is_wrong
caught the window rule stops the whole form -> test_a_rule_across_fields_holds_back_one_field
caught the roster rule left to the database -> test_a_copy_keeps_what_it_copied_when_a_field_is_wrong
caught a published title emptied -> test_a_published_one_keeps_its_required_fields
caught every save arranges its tasks again -> test_saving_again_and_again_arranges_each_task_once
caught an earlier refresh counts for a later moment -> test_a_page_refresh_counts_only_at_the_same_moment
caught a later reminder counts for an earlier one -> test_an_earlier_waiting_reminder_is_enough_a_later_one_is_not
caught a reminder in the window goes at once -> test_a_reminder_due_while_editing_waits_ten_minutes
caught a reminder in the window goes at once -> test_a_tournament_reminder_waits_too
caught a reminder too close to the start never goes -> test_a_reminder_due_while_editing_waits_ten_minutes
caught scrim reminders not once -> test_saving_again_and_again_arranges_each_task_once
caught auto-finish not once -> test_saving_again_and_again_arranges_each_task_once
caught tournament reminders not once -> test_a_tournament_reminder_waits_too
restored and green; missed: none
```

浏览器（测试机）：

```
== admin
ok  新文章打第一个字就建好（分类还空着） /admin/articles/9/|有 1 项没存（其余已保存 20:55）：分类：必需字段
……
ok  新内战打标题就建好（开始时间还空着） /admin/scrims/edit/2/
ok  发布页写着还缺开始时间
ok  补上开始时间就发布了
ok  浏览器没有报错
全部走通
== pages
看了 174 个地址，0 处有问题
全部走通
```

新人走查（`journey.py`）在倒数第二次跑过（这之后只改了列表排序和走查脚本的一行）：

```
ok  点了发信，回到战队页 /teams/1/
ok  首页「我的安排」里有这场内战
ok  浏览器没有报错
全部走通
```

## 部署（正式站）

有迁移，先备份：

```
已备份到 /app/backups/sjtu-ow-20261005-211856.tar.gz（210.8 MB）
```

`deploy_ship.sh 206`（20 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
  Applying tournaments.0014_times_while_draft... OK
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 277 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

部署日志里只看到赛事那条迁移，查了 `showmigrations scrims`：`[X] 0004_start_while_draft`，数据库里那一列也确实允许空了（见下）。

正式站真实数据上只读检查：

```
pages: {'/admin/tournaments/': 200, '/admin/tournaments/new/': 200, '/admin/scrims/': 200, '/admin/scrims/new/': 200, '/admin/tournaments/edit/1/': 200, '/admin/tournaments/1/action/publish/': 200, '/admin/scrims/edit/1/': 200}
autosave form: True
tournaments_tournament.registration_opens_at may be empty: True
tournaments_tournament.registration_closes_at may be empty: True
scrims_scrim.starts_at may be empty: True
tournaments: 1 scrims: 1
```

## 没做 / 没验证

- 分队页（勾选上场、拖拽调整自动保存）、队长的战队管理和队标：207
- `enqueue_once` 只看等着的任务；正在跑的那一刻又排一个，可能多一个，任务本身到时重新读，不会多发（提醒有 `reminder_sent_at`）
- 原来已经排着的大量重复任务（自动保存以前的）不会被清掉，到时各自重新读、什么都不做
