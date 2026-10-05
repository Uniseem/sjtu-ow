# 204 做完事顺带的信，先问一句再发（报告）

## 做了什么

用户 10-05：「然后所有的发信都必须手动点发信，这个逻辑也要改！」验证码照旧自动发，到点的提醒照旧到点发，做完事顺带的信「操作完给一个「发信」确认，可以不发」，后台和前台成员自己的操作都这样（设计 10.5，v7.8）。

1. **机制**（`core/outbox.py`、`core.middleware.HeldLettersMiddleware`、`core.HeldLetter`）：
   - 登录用户的每个 POST 开一个「这件事」（`outbox.asking`，一个上下文变量）
   - 做完事顺带的 15 种信从 `core.letters.send` 换成 `outbox.hold`：在「这件事」里就把信写定存下（内容和收信人，`HeldLetter`），不发；不在（worker、命令行、测试里直接调 service）就照旧直接发
   - 同一件事给几个人一字不差的信（取消赛事给每个队长）合成一封、写几个人
   - 事情做完，页面本来要跳去哪，改成先跳到「发信」，再回到原来那里。后台里做的在 `/admin/letters/<这件事>/`，前台在 `/letters/<这件事>/`
   - 做完事人已经退出了登录（删除账号时退出临时队伍，要告诉赛事管理员）：没人可问，直接发
   - 回的不是跳转（自动保存的 JSON）：信留着等，提示里能找到
2. **「发信」页**：每封信的主题、发给谁（自己写「你自己」，多的写「某某等 N 人」）、信的样子（框里是真发出去的 HTML，和邮件样张页一样的做法）、勾选框（默认都勾上）；「发出勾选的信」只发勾了的，「都不发」一封不发。每封只能认领一次，点两下也只发一次。后台那页挂在「首页」标签下，顶栏和标签条显示做事那页所在的大类
3. **没决定就走开**：留 7 天，过了作废。个人中心顶上「有 N 件事的信还没决定发不发」，后台首页待办同一句，点进去列出来（`/letters/`、`/admin/letters/`）
4. **只有做事的人打得开**：别人、不存在的都 404；预览框的地址也一样
5. **照旧自动发的**：验证码（allauth 自己发）、SMTP 测试信、到点的（入队申请等你处理、自动关闭、赛事和内战开始提醒）、AI 巡查提醒、「要求修改内容」、群发
6. 删除账号时删掉这个人的信；`cleanup_old_data` 删 30 天前的（信上有收信人的邮箱）
7. 页面上原来写「对方会收到邮件」「已报名的人会收到邮件」的改成说做完后问要不要发（战队管理、赛事和内战取消确认页、队伍编排、整队报名说明、后台手册）；撤下头像、取消赛事内战的提示不再说「已发信」。顺带改了两处 201 起就过时的话：README 里「改了比赛时间报了名的人会收到」，后台手册里「改开始时间会通知报名的人」
8. 后台手册、README、`docs/admin.md` 4.1、设计 10.1、10.5、附录 D

## 测试

`core/tests/test_held_letters.py`（17 条）：

- 不在网页里直接发；在网页里写定存下、内容和预览一致
- 同样的信合成一封（真取消一场赛事：三个人一封信）；只发勾了的、只发一次；两个请求同时点也只发一次；7 天作废
- 到点的提醒在网页里照旧直接发
- 15 种信都走 `hold`（看源码；换回 `send` 就红）
- 没人可问时直接发；删账号删信；每天的清理删 30 天前的
- 真走页面（`transaction=True`，信在提交后写，和正式环境一样在请求里面）：成员申请入队 → 跳到「发信」 → 看到主题、队长、预览 → 发出 → 回到战队页、队长收到；「都不发」；队长打不开申请人的「发信」页、预览、随便编的地址；个人中心的提示和列表；后台取消内战 → 跳到后台的「发信」、顶栏是「活动」、首页待办有一行、发出后两个报名的人都收到

为什么要 `transaction=True`：测试默认整条包在一个事务里，`on_commit` 要等测试结束（或 `django_capture_on_commit_callbacks` 退出）才跑，那时页面已经回完了、不在「这件事」里，信就直接发了。原来那些「点了按钮、队长收到邮件」的测试就是这样照旧绿的——它们证明信的内容，证明不了正式环境里先问再发，所以这一轮的规则全靠上面这几条真走页面的测试。

其余改动的测试：`backoffice/tests/test_door.py` 给新地址的 `<uuid:batch>` 填一个值；账号删除、个人信息导出的覆盖表各加一行；`letters` 加进保留网址。

## 命令输出

（所有检查都在测试机上跑。）

测试机整组检查（最后一次，改完全部以后）：

```
== ruff (10:42:14)
All checks passed!
398 files already formatted
== pytest (10:42:15)
1875 条测试分成 4 片
分片 1：469 passed in 56.74s
分片 2：469 passed in 57.10s
分片 3：469 passed in 60.36s (0:01:00)
分片 4：468 passed in 51.04s
== 迁移 (10:43:21)
No changes detected
== 生产配置 (10:43:23)
System check identified no issues (0 silenced).
== 错误页和模板一致 (10:43:24)
== Docker 镜像 (10:43:25)
构建成功：a4b2dc8343c4
== 全部通过 (10:43:25)
```

第一次整组（新测试写完、还没修覆盖表时）红了 5 条，都是「新东西要登记」的守卫：

```
FAILED accounts/tests/test_gone_applicants.py::test_every_column_pointing_at_a_person_has_a_fate_on_deletion
FAILED backoffice/tests/test_door.py::test_every_back_office_page_keeps_out_whoever_its_tab_is_not_for
FAILED core/tests/test_admin_wording.py::test_every_back_office_address_goes_through_the_door
FAILED accounts/tests/test_export_coverage.py::test_every_column_pointing_at_a_person_is_accounted_for
FAILED content/tests/test_content.py::test_every_fixed_top_level_route_is_reserved
```

改法：`HeldLetter.actor` 登记进删账号和导出的两张表（删账号时删信）；后台的两页挂到「首页」标签下（守卫要求每页有标签）、`test_door` 给 `<uuid:batch>` 填值；`letters` 加进保留网址。新测试第一次跑红了 2 条：同一封信第二次写没合并（存进数据库的元组变成了列表，比不上，`freeze` 改成按数据库的样子写），测试里内战取消的网址名写错。

变异（测试机，`mutate.py`）。第一次 19 处里漏了一个配对：

```
MISSED the same letter twice is two -> test_an_admin_cancels_a_scrim_and_is_asked_in_the_back_office
```

配错了：取消内战是一次把同一封信写给所有人，用不到合并；要合并的是取消赛事（每个人写一次）。加了真取消一场赛事的测试换上，重跑：

```
mutations: 19 not applying: none
baseline green, 17 tests
caught the same letter twice is two -> test_the_same_letter_to_more_people_is_one_letter
caught the same letter twice is two -> test_a_cancelled_tournament_is_one_letter_to_all_its_people
caught a letter sent twice -> test_two_clicks_at_once_send_once
……（25 个配对全部 caught）
restored and green; missed: none
```

浏览器（测试机）：

```
== admin
ok  保存编队
ok  编完问要不要给编进的人发信 true|1|发这封信 发给 截图队员、队员0、队员1（3 人，每人一封） 主题 已编入临时队伍：截图个人杯 信的样子
ok  选了都不发，回到编队页
ok  新队伍出现在页面上
……
ok  浏览器没有报错
全部走通
== journey
ok  申请了战队
ok  申请后问要不要给队长发信 true|1
ok  点了发信，回到战队页 /teams/1/
ok  首页「我的安排」里有这场内战
ok  浏览器没有报错
全部走通
== pages
看了 174 个地址，0 处有问题
全部走通
```

截图（测试机，1280 宽）看过：前台「发信」页（勾选框、发给、主题、框里是真信）、后台「发信」页（顶栏「活动」、标签「内战」、两封信合在一页、第二封的信样收着）、还没发的信列表。

## 部署（正式站）

有迁移，先在服务器上备份：

```
-rw-r--r-- 1 root root 221059214 Oct  5 10:42 sjtu-ow-20261005-184226.tar.gz
```

`deploy_ship.sh 204`（41 个文件）：

```
 Image sjtu-ow-web Built
 Image sjtu-ow-worker Built
  Applying core.0023_heldletter... OK
 Container sjtu-ow-worker-1 Started
全量生成完成：成功 12，失败 0，删除 0；目录占用 277 KB
{"status": "ok", "checks": {"database": {"ok": true, "detail": "ok"},
```

正式站真实数据上只读检查：

```
pages: {'/admin/letters/': 200, '/admin/': 200, '/letters/': 200, '/me/': 200}
table: True
held rows: 0 waiting for root: 0
middleware: True
```

（备份时 ssh 连接被对方断开，`backup` 已经写完；等部署结束的循环把自己的命令行当成了还在跑的部署脚本、一直等，手动停了，部署本身正常结束。）

## 没做 / 没验证

- 15 种信里只有申请入队、编队、取消内战、取消赛事真的从页面或 service 走过「先问」；其余 11 种靠「源码里是 `hold`」那条测试和同一套机制，没有逐个走页面
- 回 JSON 的操作（自动保存）如果顺带写了信，信留着等、不跳转；现在没有哪个自动保存会写这 15 种信，所以这条路没有页面测试
- 原来那些「点了按钮、收到邮件」的测试照旧绿，是因为测试里 `on_commit` 在页面回完之后才跑（见上），它们测的是信的内容
