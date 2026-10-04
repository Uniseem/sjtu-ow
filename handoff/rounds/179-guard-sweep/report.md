# 179 守卫普查：059 之后加的守卫也逐个拆一遍（报告）

## 做了什么

1. `mutate_guards.py` 从 042 复制到本轮目录（042 的文件没改），应用清单加上 `comments`、`search`。列出来是 254 个守卫
2. 在测试机上单独开了一个工作树后台跑（`/srv/sjtu-ow-check/sweep`，不占 `remote-check.sh` 的锁），3 个并行。结果原样存在 `results.jsonl`，过程在 `sweep-log.txt`
3. 35 个没被抓到的逐个看了：29 个是真没测到，补了测试；6 个改了也测不出来，理由在下面
4. 顺着 SSRF 那条看了字体下载跟随跳转时的检查（`_SafeRedirectHandler`，不是 `if`，普查看不到），也没有测试，一起补了
5. 补的 30 处写进 `mutate.py`，在测试机上逐个改坏，全部被抓到
6. 跑完后删了测试机上的普查工作树和 44 MB 的临时副本

这一轮只加测试，没有改网站代码，也没改设计。

## 普查结果

| | 个数 |
|---|---|
| 守卫 | 254（core 64、tournaments 52、teams 39、accounts 33、scrims 28、comments 19、content 7、members 4、moderation 4、sjtu_ow 3、search 1） |
| 本应用的测试就抓到 | 204 |
| 本应用没抓到、全量测试抓到 | 15 |
| 全量测试也没抓到 | 35（core 14、accounts 9、teams 4、tournaments 4、comments 2、content 2） |

`scrims` 的 28 个守卫全部被抓到，`members`、`moderation`、`search`、`sjtu_ow` 也是。每个变异的耗时加起来 207.8 分钟。基线（未变异、3 个同时跑）每份 1650 条全过，167–171 秒。

## 补了测试的 30 处（普查的 29 处，加上跳转检查）

按「改坏了会怎样」排：

**安全和权限**

| 守卫 | 改坏的后果 | 测试 |
|---|---|---|
| `core/net.py:46` 地址指向内网就拒绝 | 字体下载可以让服务器去访问 `127.0.0.1`、`10.x`、云服务器元数据 `169.254.169.254`（SSRF）。这一条的测试是跟着 067 删 Webhook 一起没的，之后一直没有 | `core/tests/test_security_guards.py`：5 个字面地址、一个域名解析到内网 |
| `core/fonts/download.py:41` 跳转到的地址也要检查 | 公网地址回一个 302 指向内网，服务器跟着跳过去。普查只找 `if`，这一行它看不到 | `…::test_a_redirect_into_our_network_is_refused` |
| `comments/services.py:137` 恢复隐藏要内容编辑权限 | 普通成员能把编辑藏起来的评论恢复 | `comments/tests/test_comment_extras.py::test_readers_cannot_undo_what_editors_did` |
| `comments/services.py:266` 取消置顶同上 | 普通成员能取消置顶 | 同上 |
| `teams/services.py:469` 指定队长不能指定停用的账号 | 站长的「指定新队长」（177）可以把队交给另一个登录不了的账号 | `teams/tests/test_teams.py::test_superuser_can_assign_a_captain` 加一段 |
| `accounts/models.py:24、45、47` 建账号要邮箱、超级管理员要两个标志 | `createsuperuser` 之类能建出没邮箱的账号、或者 `is_staff=False` 的「超级管理员」 | `accounts/tests/test_guards_left_open.py` |

**数据和运维**

| 守卫 | 改坏的后果 | 测试 |
|---|---|---|
| `core/management/commands/restore.py:160` 备份里没有 `db.sqlite3` 就停 | 只有上传文件的包也会往下走，`sqlite3` 打开不存在的文件会建一个空库 | `core/tests/test_ops_commands.py::test_an_archive_without_a_database_is_refused` |
| `core/management/commands/backup.py:106` 同名备份已经存在就停 | 同一秒的第二次备份覆盖前一份 | `…::test_a_second_backup_in_the_same_second_does_not_overwrite`（固定时间） |
| `core/offsite.py:133` 没开启就不上传 | 上传函数本身不看开关（只有 `backup` 命令看） | `core/tests/test_offsite_backup.py::test_upload_itself_refuses_when_the_feature_is_off` |
| `core/offsite.py:193、242、269` 配置不全时列出、清理、下载直接说缺什么 | 报对象存储客户端的错，看不出缺哪一项 | `…::test_listing_pruning_and_fetching_say_what_is_missing` |
| `core/health.py:76` 健康检查读回刚写的探测行 | 写了读不回来也报正常 | `core/tests/test_pages.py::test_a_write_that_does_not_show_up_fails_the_check` |
| `core/mail.py:247` SMTP 没收下测试邮件就报错 | 「发送测试邮件」按钮在什么都没发出去时也说成功 | `core/tests/test_mail.py::test_a_test_email_the_server_did_not_take_is_an_error` |
| `core/translations.py:34、39、50` `.po` 格式错就停 | 手改的后台翻译写错了，编译读一半照样生成 `.mo` | `core/tests/test_admin_wording.py::test_a_broken_po_file_is_refused_not_half_read` |
| `core/fonts/forms.py:78、139` 先看字体文件大小再读 | 超过 30 MB 的文件先整个读进内存，再被 `inspect_font` 拒绝 | `core/tests/test_fonts.py::test_an_oversized_upload_is_refused_before_it_is_read`（把 `inspect_font` 换成一调用就失败） |
| `content/management/commands/load_legal_pages.py:108` 没有协议页先提示跑 `init_site` | 报 `AttributeError` | `content/tests/test_legal_pages.py::test_the_command_asks_for_init_site_first` |
| `content/services.py:69` 没有默认站点 | README 说改了 `SITE_URL` 在 shell 里跑这个函数，没有站点时报 `AttributeError` | `content/tests/test_submissions.py::test_site_hostname_sync_says_when_there_is_no_site` |

**赛事、头像、段位**

| 守卫 | 改坏的后果 | 测试 |
|---|---|---|
| `tournaments/registration.py:147` 有队员没填游戏 ID | 入队要游戏 ID，但入队后能删掉；整队报名时这个人会带着空的游戏 ID 进名单 | `tournaments/tests/test_registration.py::test_check_7_a_member_who_removed_every_game_id` |
| `tournaments/registration.py:757` 编排页提到的队伍已经不在 | 两个管理员同时开编排页，一个解散了队，另一个保存时 500 | `tournaments/tests/test_adhoc_teams.py::test_saving_a_board_that_names_a_dissolved_team` |
| `tournaments/registration.py:941` 不在报名中的临时队伍不能退出 | 解散只把人放回散人池、名单行留着做记录；旧页面上的「退出」照样能删掉名单行，最后一人还会再「解散」一次 | `…::test_nobody_leaves_a_team_that_was_already_dissolved` |
| `tournaments/teams_admin.py:54` 编排页标「人数不足」 | 有人退出后队伍低于下限，编排页不提示 | `…::test_the_board_flags_a_team_that_fell_below_the_minimum` |
| `accounts/services.py:762` 图片没了的头像不能通过 | 图片在图片库里被删后通过审核，头像指向不存在的图片 | `accounts/tests/test_guards_left_open.py` |
| `accounts/services.py:809` 只能撤下正在用的头像 | 撤下一张旧的、已经换掉的头像会把现在的头像也清掉 | 同上 |
| `accounts/ranks.py:45` 段位分数超出 0–39 | `-1`、`41`、字符串、小数照样解码 | 同上 |

测试都用的是「不该有这个权限」的人（评论用普通成员，头像审核用内容编辑），没用超级管理员测权限；`assign_captain` 本来就只许超级管理员，测的是被指定的人。

## 改了也测不出来的 6 处

| 守卫 | 理由 |
|---|---|
| `accounts/forms.py:189` 游戏 ID 已被占用（表单） | 模型的 `clean()`（`accounts/models.py:255`）查同一件事，库里还有唯一约束。拆掉一层，另一层给出同样的提示 |
| `accounts/models.py:255` 同上（模型） | 同上 |
| `accounts/ranks.py:48` 段位档不在表里 | 45 行已经把分数限定在 0–39（40 是前 500，在更前面处理），`divmod(score, 5)` 只能得到 0–7，八档都在表里，走不到 |
| `teams/forms.py:94` 申请至少选一个位置（表单） | `teams/services.apply_to_team` 查同一条、同样的提示，视图把 `TeamError` 显示出来 |
| `teams/services.py:121` 建队时重名 | 库里有 `unique_active_team_name`（`Lower("name")`，只算没解散的队），插入失败在 136 行转成同样的 `NAME_TAKEN` |
| `teams/services.py:156` 改队名时重名 | 同上，169 行 |

## 命令输出

普查（测试机，`sweep-log.txt` 开头和最后几行）：

```
基线（并行负载下，未变异）：
  w0: exit=0 1650 passed, 2 deselected in 167.49s (0:02:47) []
  w1: exit=0 1650 passed, 2 deselected in 171.37s (0:02:51) []
  w2: exit=0 1650 passed, 2 deselected in 170.81s (0:02:50) []
[1/254] ✓ accounts/forms.py:133 ProfileForm.clean_motto  if LINK_IN_TEXT.search(motto)
[2/254] ✗ accounts/forms.py:189 GameAccountForm.clean_battletag  if qs.exists()
…
[253/254] ✓ tournaments/wagtail_hooks.py:272 manager_required.wrapper  if not services.can_manage(request.user)
[254/254] ✓ tournaments/wagtail_hooks.py:281 tournament_action  if action not in ACTIONS
```

变异（测试机，30 处、31 次，全部被抓到）：

```
baseline green, 23 tests
caught no email accepted -> test_accounts_need_an_email_and_superusers_both_flags
caught superuser without is_staff -> test_accounts_need_an_email_and_superusers_both_flags
caught superuser without is_superuser -> test_accounts_need_an_email_and_superusers_both_flags
caught any score decoded -> test_scores_outside_the_table_are_refused
caught vanished picture approved -> test_a_picture_that_vanished_cannot_be_approved
caught old face taken down -> test_only_the_face_in_use_can_be_taken_down
caught readers unhide -> test_readers_cannot_undo_what_editors_did
caught readers unpin -> test_readers_cannot_undo_what_editors_did
caught legal pages without init_site -> test_the_command_asks_for_init_site_first
caught no default site -> test_site_hostname_sync_says_when_there_is_no_site
caught big upload read -> test_an_oversized_upload_is_refused_before_it_is_read
caught big weight read -> test_an_oversized_upload_is_refused_before_it_is_read
caught probe not read back -> test_a_write_that_does_not_show_up_fails_the_check
caught unsent test email -> test_a_test_email_the_server_did_not_take_is_an_error
caught backup overwritten -> test_a_second_backup_in_the_same_second_does_not_overwrite
caught restore without a database -> test_an_archive_without_a_database_is_refused
caught internal address fetched -> test_addresses_inside_our_network_are_refused
caught internal address fetched -> test_a_name_that_resolves_inside_is_refused_too
caught upload while off -> test_upload_itself_refuses_when_the_feature_is_off
caught listing half configured -> test_listing_pruning_and_fetching_say_what_is_missing
caught pruning half configured -> test_listing_pruning_and_fetching_say_what_is_missing
caught fetching half configured -> test_listing_pruning_and_fetching_say_what_is_missing
caught orphan .po line -> test_a_broken_po_file_is_refused_not_half_read
caught doubled .po keyword -> test_a_broken_po_file_is_refused_not_half_read
caught entry without msgid -> test_a_broken_po_file_is_refused_not_half_read
caught stopped account made captain -> test_superuser_can_assign_a_captain
caught member without a game ID registered -> test_check_7_a_member_who_removed_every_game_id
caught stale board crashes -> test_saving_a_board_that_names_a_dissolved_team
caught leaving a dissolved team -> test_nobody_leaves_a_team_that_was_already_dissolved
caught short team not flagged -> test_the_board_flags_a_team_that_fell_below_the_minimum
caught redirects followed anywhere -> test_a_redirect_into_our_network_is_refused
restored and green; missed: none
```

整组检查（测试机）：

```
== pytest (07:27:06)
1688 条测试分成 4 片
分片 1：422 passed in 52.19s
分片 2：422 passed in 44.75s
分片 3：422 passed in 44.77s
分片 4：422 passed in 42.52s
== 迁移 (07:28:03)
No changes detected
== 生产配置 (07:28:04)
System check identified no issues (0 silenced).
== 错误页和模板一致 (07:28:05)
== Docker 镜像 (07:28:06)
构建成功：f98d1be46d92
== 全部通过 (07:28:06)
```

## 没做

- 普查只找「条件成立就拒绝」的 `if`。模板里的条件、查询里的过滤（比如 177、178 那种 `user__is_active=True`）不在里面，那些靠每轮自己的变异
