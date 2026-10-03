# 116 前台管理页：复查第二部分（成员这边）（报告）

## 做了什么

1. **战队管理页**（`teams/templates/teams/manage.html`、`teams/views.py`）：成员表加「位置与段位」（`play_style` 组件，和战队主页一样）；申请卡列出每个游戏 ID 和段位（新过滤器 `rank_summary`：「坦克 黄金 2 · 输出 黄金 1」，没有段位写「未定级」）；成员和申请一次取出游戏 ID（原来逐行查）；解散一块：有进行中的报名时列出原因、按钮写「暂时不能解散」并置灰，没有才出现确认的表单；空的申请列表用 `empty_state`；四个 `section_head` 去掉不认的 `index=`
2. **创建战队**：`teams.services.create_blocker()` 把权限和队长上限的检查抽出来，`create_team` 和页面共用；页面有原因时只显示原因和「回到我的战队」；建队、改资料失败时删掉先存的队标（`_drop_unused_logo`）；队名重复（`NAME_TAKEN`，四处同一句）写到队名一栏，其他原因写在表单上面，不再是几秒就消失的提示
3. **报名**：名单快照加「段位（提交时）」（快照里本来就存着）；后台报名详情的段位用新过滤器 `rank_label`
4. **我的报名**：`my_registrations` 加 `members__is_active=True`；个人报名表加游戏 ID（删了的写「游戏 ID 已删除」）、按钮「取消个人报名」、状态分已编入 / 赛事已取消 / 赛事已结束没有编队 / 等待编队；空列表用 `empty_state`
5. **账号页**：新片段 `account/_back_to_security.html`（位置导航）放进改密码、改邮箱、邮箱地址、设置密码四页；「账号安全」加一行退出登录（POST 表单）；导出链接两处改用 `data-no-loading`
6. **注册页**：同意框下面一句话链到 `/terms/`、`/privacy/`
7. **说法**：内战被禁止用 `feature_denied_message`；`member_problems` 加 `as_self`，个人报名传 `True`（「你的资料不完整」「你暂时无法使用此功能…」），战队报名里说队员仍用昵称；新片段 `components/profile_gap_links.html`（「去补全：游戏 ID、联系方式」）放进内战报名区、个人报名页、申请入队页
8. **评论**：`_section_response` 不再把 `can_post` 设成否，问题去重后加在原有问题前面；顶层评论被拒时把打的字放回输入框（回复的不放，免得跑到顶层输入框里）
9. **我的战队**：两个空列表用 `empty_state`；报名详情两个 `section_head` 去掉不认的 `en=`

## 命令输出

变异（`mutate.py`，18 处）。第一次漏了两处：注册页的协议链接（页脚每页都有 `/privacy/`，测试改成只看注册表单里）、我的战队的空状态（同一页还有另一个空状态，测试改成认标题）。整组重跑：

```
baseline green, 13 tests
caught members without positions and ranks -> test_the_captain_sees_ranks_of_members_and_applicants
caught applicants without ranks -> test_the_captain_sees_ranks_of_members_and_applicants
caught disband blockers hidden until the button -> test_a_team_that_cannot_disband_says_why_before_the_button
caught the create page shows the form anyway -> test_the_create_page_says_no_before_the_form
caught a refused team keeps its logo -> test_a_refused_team_leaves_no_logo_and_names_the_field
caught the snapshot has no ranks -> test_the_roster_snapshot_and_the_admin_show_ranks
caught the admin shows rank codes -> test_the_roster_snapshot_and_the_admin_show_ranks
caught rosters I left are listed -> test_my_registrations_lists_rosters_i_am_on_and_my_signups_in_full
caught a finished tournament still waits for a team -> test_my_registrations_lists_rosters_i_am_on_and_my_signups_in_full
caught the password page has no way back -> test_password_and_email_pages_lead_back_to_account_security
caught no logout on account security -> test_password_and_email_pages_lead_back_to_account_security
caught signup without the agreement links -> test_signup_links_the_agreement_and_the_privacy_policy
caught the export is a download attribute again -> test_the_export_link_is_not_a_download_attribute
caught an individual signup calls you by name -> test_an_individual_signup_speaks_to_the_person
caught signup notices without links -> test_signup_notices_link_to_where_the_profile_is_filled_in
caught a refused comment loses the box -> test_a_refused_comment_keeps_the_box_and_the_text
caught a refused comment loses the text -> test_a_refused_comment_keeps_the_box_and_the_text
caught no teams is a bare sentence -> test_empty_lists_use_the_empty_state
restored and green; missed: none
```

改了三条原有测试的断言：内战和个人报名被禁止的说法（换成标准说法）、导出链接的标记（106 的测试原来要求 `download`，改成要求 `data-no-loading`）。

整组检查（开发服务器停着）：

```
All checks passed!
285 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
```

第一次全量红了 `core/tests/test_transitions.py::test_downloads_are_marked_so_the_bar_skips_them`（就是上面说的 106 的测试），改了断言。第二次：

```
1379 passed in 306.63s (0:05:06)
```

本机截图（队长身份）：战队管理页的成员表有「位置与段位」（全能、支援、坦克，带段位），申请卡下面是「Nobody#6060：坦克 黄金 2 · 输出 黄金 1 · 支援 黄金 3」。

演示站（镜像时间 `2026-10-03T15:39:16+02:00`）：

```
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
```

## 没做 / 未验证

- 内战报名出错就地显示（见请求「不做」）
- 入队申请表的「缺」标记
- 手机宽度下的战队管理页（成员表多了一列）没截图
