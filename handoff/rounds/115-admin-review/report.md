# 115 后台和管理页面全面复查，先修安全和会坏的（报告）

## 复查

见 `findings.md`。做法：本机临时超级管理员打开后台菜单 32 项和每个列表的第一个对象（除全站设置是 302 跳到带编号的地址、帮助里两个外部链接，都是 200），无头 Edge 逐页截图；五个后台角色各建临时账号读侧边栏、试开 22 个页面（事务里建、跑完回滚）；队长身份截图 13 个前台管理页；两个只读子代理对照设计审后台和前台管理页代码（子代理读代码得出的结论，修之前我都复现或读代码确认过）。复查用的临时超级管理员（`review-admin@local.test`）只在本机开发库里，后面几轮复查还要用，修完再删。

## 修了什么（`findings.md` 第一部分，11 条）

1. **删除**：赛事、内战各加一个权限策略（对象级「删除」看 `can_delete`）和一个删除页（打开就检查，不行就带着原因回编辑页）；列表页的删除链接也按 `can_delete` 出现（Wagtail 的列表只看模型级权限）。赛事：只有从没发布过的草稿能删（原有规则，之前没接上）；内战：新加 `scrims.services.can_delete`，只有没人报名的草稿。两个后台操作地址里写不存在的操作给 404（原来 KeyError 500）。权限策略用 `register_permission_policy` 注册（放在 viewset 上 Wagtail 9 要去掉，启动时有警告）
2. **后台帐号页**：`WAGTAIL_EMAIL_MANAGEMENT_ENABLED = False`；Wagtail 没有去掉默认面板的钩子，在 `accounts/wagtail_hooks.py` 里把「名字和邮箱」「头像」两个面板的 `is_active` 设为否
3. **用户后台**（`accounts/admin_users.py`、`accounts/users_app.py`、`accounts/templates/accounts/admin/user_edit.html`）：`INSTALLED_APPS` 里用 `SiteUsersAppConfig` 代替 `wagtail.users`（同一个应用标签），指向自己的 `SiteUserViewSet`：表单去掉「名」「姓」、加昵称、是否交大、停用原因（从启用变停用时必填）；编辑页「在社区里」一块列出邮箱是否验证、常用位置、游戏 ID 和段位、联系方式（超级管理员或有查看联系方式权限的人）、战队、功能权限规则；保存时从启用变停用，调用新的 `accounts.services.after_deactivation` 取消待审批的入队申请；新建页、删除页直接拒绝，列表上不出现「添加用户」和删除链接。模板名要设在 viewset 上（`edit_template_name`），设在视图上会被 viewset 覆盖，第一次就是这样没生效
4. **报名审核**：列表加上一页、下一页链接（带着筛选）；批量通过后的跳转用 `url_has_allowed_host_and_scheme` 检查；`registration.reject` 对临时队伍直接拒绝（「请在队伍编排里调整」）；导出 CSV 只读导出的这些报名里的人的联系方式
5. **备份密钥**：`core/forms.py` 把只写的处理抽成 `SECRET_FIELDS`，SMTP 密码和备份密钥都用密码框、不回填，留空保留原值；两个英文标签改中文；顺手改正 `moderation_daily_limit` 的帮助文字（超额是排到第二天，设计和代码都是这样）
6. **游戏 ID、联系方式页**：新增表单的目标改成它自己的那个格子（出错只换表单，列表还在）；保存成功用 `HX-Retarget` 换掉整个列表；`取消`（不带 `?new` 的 HTMX 请求）只回列表；删除被拦时加一条消息、回 200 的列表，`me/_htmx_oob.html` 带上消息区，提示显示成弹出提示；删除按钮改成真正的表单（`hx-post` 加在表单上，没有脚本也能提交）
7. **删除已结束赛事用过的游戏 ID**：`IndividualSignup.game_account` 改成可空、删除时置空（迁移 `tournaments/0009`）；导出个人信息和编排页对空值显示「游戏 ID 已删除」。设计 12.8.4 那行同步改了
8. **战队后台**：权限策略对「新建」「删除」一律否；编辑页保存后调用 `on_team_changed`（重新生成页面、送 AI 审核，和队长自己改一样）；表单加「缺的位置」三个勾选框；「招募中」列显示成图标；`assign_captain` 拒绝已解散的队、停用的账号、满员时的新成员；指定队长页改成按昵称或邮箱搜（最多列 50 人），已解散的队不出现「指定队长」
9. **评论后台**：权限策略对「新建」「删除」一律否；编辑页加只读的全文、作者、文章、时间；列表的两个布尔列显示成图标；列表一次取出作者和文章（原来逐行查）
10. （同第 4 条）
11. **确认**：`static/js/app.js` 加一个监听：表单带 `data-confirm` 就先问；前台 15 处表单加上（退出战队、撤回申请、从退役名单去掉、转让队长、移除成员、解散战队、撤回报名、退出临时队伍、取消个人报名两处、取消内战报名、撤回待审头像、改用默认头像）；后台三处用 `onsubmit`（后台的内容安全策略允许）：编排页解散临时队伍、清空全部静态文件、删除字重

## 命令输出

变异（`mutate.py`，28 处）。前三次各有漏网的，都是测试测得不够准：

- 「成员能在后台改邮箱」：名字和邮箱整个面板已经关了，只关设置看不出来，补了直接断言 `email_management_enabled()` 是否
- 「备份密钥显示出来」：只去掉字段声明，初始值仍被清空，页面上照样看不到，补了「这个字段是密码框」
- 「新增出错换掉整个列表」：测试找的 `hx-target="#create-contact"` 其实是「新增联系方式」按钮上的，改成取出表单标签本身再看
- 「评论编辑页看不到全文」：评论的前 20 个字会出现在页面标题里，改用更长的评论、断言后半句

另有两条变异的原文在文件里出现两次（内容同样的 `hx-target` 段落、两个 `SET_NULL` 字段），加了上下文。最后整组：

```
baseline green, 21 tests
caught published tournaments can be deleted -> test_a_published_tournament_cannot_be_deleted
caught the listing offers delete for published ones -> test_a_published_tournament_cannot_be_deleted
caught scrims with signups can be deleted -> test_a_scrim_with_signups_cannot_be_deleted
caught an unknown action crashes -> test_an_unknown_action_is_not_found
caught members change their email in the admin -> test_members_cannot_change_their_login_email_in_the_admin
caught the admin asks for first and last name -> test_members_cannot_change_their_login_email_in_the_admin
caught the admin takes an unreviewed face -> test_members_cannot_change_their_login_email_in_the_admin
caught Wagtail's own user screens -> test_the_user_page_has_the_sites_fields_not_first_and_last_name
caught stopping needs no reason -> test_stopping_an_account_needs_a_reason_and_cancels_its_applications
caught stopping leaves applications pending -> test_stopping_an_account_needs_a_reason_and_cancels_its_applications
caught users can be added in the admin -> test_users_are_not_added_or_deleted_in_the_admin
caught no page links on the review list -> test_the_review_list_links_to_its_other_pages
caught bulk approve follows any address -> test_bulk_approve_stays_on_the_site
caught ad-hoc teams can be rejected here -> test_an_adhoc_team_is_not_rejected_from_the_review_page
caught the backup secret is shown -> test_the_backup_secret_is_never_shown_and_blank_keeps_it
caught a mistake replaces the contact list -> test_a_mistake_in_the_new_contact_form_keeps_the_list
caught a new contact does not refresh the list -> test_a_mistake_in_the_new_contact_form_keeps_the_list
caught cancel puts the page in the list -> test_cancel_brings_back_the_list_not_the_whole_page
caught deleting an old tournament's game ID crashes -> test_a_game_id_from_a_finished_tournament_can_be_deleted
caught teams can be deleted in the admin -> test_teams_are_not_added_or_deleted_in_the_admin
caught captains go to disbanded teams -> test_a_captain_is_not_assigned_to_a_disbanded_or_full_team
caught captains overfill a team -> test_a_captain_is_not_assigned_to_a_disbanded_or_full_team
caught admin team edits regenerate nothing -> test_an_admin_edit_of_a_team_regenerates_its_pages
caught comments can be deleted in the admin -> test_comments_are_hidden_or_pinned_not_added_or_deleted
caught the comment edit page hides the comment -> test_comments_are_hidden_or_pinned_not_added_or_deleted
caught disbanding asks nothing -> test_forms_that_take_something_away_ask_first
caught the script ignores the question -> test_the_site_script_asks_the_forms_question
caught clearing static files asks nothing -> test_admin_forms_that_take_something_away_ask_first
restored and green; missed: none
```

原有测试改了一条：`test_a_pooled_game_id_cannot_be_deleted` 原来断言被拦时是 400（htmx 不会显示 400，就是这个 bug），改成断言回列表、带弹出提示、游戏 ID 还在。

整组检查（开发服务器停着）：

```
All checks passed!
284 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

第一次全量跑红了一条 `scrims/tests/test_scrims.py::test_a_game_id_used_by_a_live_scrim_is_still_refused`：也是断言被拦时 400，同样改成断言回列表和提示。第二次红了 `core/tests/test_prerender.py::test_state_fragment_is_rate_limited`，单独跑是绿的：限流按整分钟计数，全量跑得慢时循环跨过了整分钟、计数重来。测试里把时钟固定住。第三次：

```
1366 passed in 268.41s (0:04:28)
```

本机截图（迁移后重启 `runserver`）：用户编辑页是邮箱、昵称、是否来自交大、有效、停用原因和「在社区里」一块；评论编辑页上面是只读的内容、作者、文章、时间；战队编辑页多了缺的位置；后台帐号页只剩区域、主题和通知。

演示站（镜像时间 `2026-10-03T14:39:58+02:00`）：

```
Running migrations:
  Applying core.0015_settings_labels... OK
  Applying tournaments.0009_individual_signup_game_account_set_null... OK
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
```

## 没做 / 未验证

- `findings.md` 第二、三部分（下一轮起）；第五部分等你定
- 后台帐号页剩下的「Theme preferences」「Admin theme」等英文是 Wagtail 自己没翻译的，放在界面文字那一轮
- 演示站上浏览器里的后台操作：登录要 HTTPS
