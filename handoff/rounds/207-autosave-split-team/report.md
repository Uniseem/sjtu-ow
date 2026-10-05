# 207 自动保存（下之二）：分队页、队长的战队管理（报告）

## 做了什么

用户 10-05：「继续做 207」。设计 13.17 里自动保存的最后两块（设计 v7.11）。到这一轮，后台和个人中心改值的地方都自动保存了；队伍编排页的「保存编队」仍是按钮（会发信，10.5）。

1. **分队页**（`scrims/split_admin.py` 的 `_autosave`、`static/js/scrim-split.js`）：
   - 勾选上场改了就存（表单 `data-autosave`，带 `part=pick`）；存好后「分队结果」那一块整块换回来，取消勾选的人从板上拿掉。为此把分队结果和复制结果拆成 `_board.html`、`_copy.html`、`_problem.html`
   - 拖拽或卡片按钮每动一次就存（`part=teams`）：脚本改的是隐藏框，不会自己发事件，`moved()` 在真的动了以后给表单里的 `[data-teams-moved]` 发一个 `change`；存好后复制文字和两队「位置人数不符」跟着换
   - 「保存上场名单」「保存分队」只在没有脚本时出现；「生成分队」照旧是按钮（点之前先把勾选存好）
   - 操作记录：勾选、调整各自 30 分钟内合成一条（`autosave.log_edit`，原来每点一次保存一条）
2. **自动保存脚本**（`static/js/autosave.js`）：
   - 换进来的页面片段里有自动保存的表单，接着接上；换完发一个 `ow:replaced` 事件，分队页的脚本听到后给新板子接上拖拽、复制按钮
   - 被换掉的表单不再存（它手里的东西是旧的，存上去会把刚换进来的改回去，比如把刚取消勾选的人又勾回去）
   - 回的 `values` 能清空文件框、改勾选框（原来只改文字框）；文件框、勾选框不管有没有焦点都改
3. **队长的战队管理**（前台，`teams/views.py` 的 `_autosave_profile`）：
   - 「战队资料」改了就存；有问题的字段不存（重名在表单里就查，写在队名下面），别的照存
   - 选好队标文件就上传换上；勾「删除队标」就删；页面上加了「现在的队标」（`teams/_logo.html`，原来管理页上看不到队标），换了跟着变；存好后文件框清空、「删除队标」取消勾选，下一次保存不会再传一遍、删一遍
   - 没有脚本时「保存」按钮还在
4. 设计 13.17、9.5、7.1、附录 D；`docs/admin.md` 4.3；README 分队、改了就存两处

## 测试

`core/tests/test_autosave_split_team.py`（6 条）：

- 取消勾选：存上，那人不再上场、队伍清空；回的分队结果里没有他、有别人，换进来的表单带 `data-autosave`
- 移到缓冲区：存上（仍是上场的人），复制文字里没有他了，两队的「位置人数不符」都回来了
- 勾选、调整各三次：操作记录各一条
- 分队脚本在动了以后给表单发 `change`（看源码；拿掉就不会自动保存）
- 战队资料：重名不存、简介照存
- 队标：选了就传上、页面显示、文件框清空；再存别的不会再传；勾删除就删、取消勾选

改的旧测试：`teams/tests/test_teams.py` 三条只建表单的队标测试加了数据库（队名现在在表单里查重）。

浏览器（干部那一晚）分队一段改成按自动保存走，并加了：移到缓冲区刷新还在、移回来也存上了、取消勾选的人马上从分队结果里拿掉、换上来的分队结果照样每动一次就存、战队资料改了就存刷新还在、队标选好就换上文件框清空了（真的用浏览器选文件，`DOM.setFileInputFiles`）。

## 命令输出

（所有检查都在测试机上跑；本机只改文件。）

第一次：测试数据里的段位分数写了 2000（不是合法的段位）、队标测试没建图片集合（`KeyError: 'collection'`）；一个没用的导入、一行太长、两个文件要重新排版（在测试机上 `ruff format`，差异拿回本机套上）。改好后：

```
All checks passed!
402 files already formatted
232 passed in 18.27s
```

整组检查：

```
== ruff (13:54:36)
All checks passed!
402 files already formatted
== pytest (13:54:37)
1900 条测试分成 4 片
分片 1：475 passed in 55.99s
分片 2：475 passed in 60.44s (0:01:00)
分片 3：475 passed in 55.65s
分片 4：475 passed in 59.32s
== 迁移 (13:55:43)
No changes detected
== 生产配置 (13:55:45)
System check identified no issues (0 silenced).
== Docker 镜像 (13:55:47)
构建成功：a4fdf300ce41
== 全部通过 (13:55:47)
```

变异（`mutate.py`，12 处）：

```
mutations: 12 not applying: none
baseline green, 6 tests
caught a tick not saved -> test_unticking_saves_and_takes_the_player_off_the_board
caught the board not sent back -> test_unticking_saves_and_takes_the_player_off_the_board
caught a move not saved -> test_a_move_saves_and_the_copy_text_follows
caught the copy text not sent back -> test_a_move_saves_and_the_copy_text_follows
caught every tick logged -> test_each_kind_of_edit_is_one_log_entry
caught every move logged -> test_each_kind_of_edit_is_one_log_entry
caught a move tells nobody -> test_a_move_on_the_board_tells_the_form
caught a taken name goes to the service -> test_a_taken_name_is_kept_and_the_rest_saved
caught the file box kept -> test_a_chosen_logo_goes_up_at_once_and_only_once
caught the logo not shown -> test_a_chosen_logo_goes_up_at_once_and_only_once
caught 「删除队标」 ignored -> test_a_chosen_logo_goes_up_at_once_and_only_once
caught a chosen logo waits for 保存 -> test_a_chosen_logo_goes_up_at_once_and_only_once
restored and green; missed: none
```

浏览器（测试机）：

```
== admin
ok  勾满 10 人后「生成分队」能点了
ok  生成了两队各 5 人 5/5
ok  移到缓冲区就存上了，刷新还在 4
ok  移回来也存上了 5
ok  取消勾选的人马上从分队结果里拿掉 True
ok  换上来的分队结果照样每动一次就存 4
ok  战队资料改了就存，刷新还在 浏览器里改的简介
ok  队标选好就换上，文件框清空了 true|
ok  三个散人移进新队伍 3
ok  保存编队
ok  编完问要不要给编进的人发信 true|1|发这封信 发给 截图队员、队员0、队员1（3 人，每人一封） 主题 已编入临时队伍：截图个人杯 信的样子
ok  选了都不发，回到编队页
ok  新队伍出现在页面上
……
ok  补上开始时间就发布了
ok  浏览器没有报错
全部走通
== journey
全部走通
== pages
看了 174 个地址，0 处有问题
全部走通
```

## 部署（正式站）

没有迁移，没删文件。`deploy_ship.sh 207`（15 个文件）：

```
 Image sjtu-ow-web Built 
 Image sjtu-ow-worker Built 
 Container sjtu-ow-worker-1 Started 
全量生成完成：成功 12，失败 0，删除 0；目录占用 277 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站真实数据上只读检查：

```
pages (status, new piece, autosave): {'/admin/scrims/1/split/': (200, True, True)}
scrims: 1 teams: 1
```

正式站上唯一的一支战队已经解散，没有能打开的战队管理页，这一页在正式站上**未验证**（测试和浏览器走查覆盖了）。

## 没做 / 没验证

- 队伍编排页（个人报名的赛事）照设计不改：「保存编队」会让编进的人收到信，仍是按钮
- 拖拽很快连着动几次：每次动都发 `change`，自动保存脚本一次只发一个、发的时候又改了就接着再发，最后存的是最后的样子；没有专门测连着拖
- 取消勾选时板子上还有没存完的移动：那一下移动不会再存（被换掉的表单不再存），以服务器那边为准
