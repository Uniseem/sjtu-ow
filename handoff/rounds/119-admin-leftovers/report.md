# 119 后台复查的剩余小项（报告）

## 做了什么

1. **操作记录**（设计 14.4）：新模块 `core/admin_log.py`（动作表 + `record()`，写失败只记日志、不影响操作本身），`core/wagtail_hooks.py` 注册动作名。写进去的：赛事的发布、标记结束、取消（带原因）、队伍编排的保存（带新建、调整、解散、移回的数量）；内战的发布、标记结束、取消、保存上场名单、生成分队（带分差）、保存分队；战队的指定队长（带新队长）、解散。在对象的「历史」页和「报告 → 网站历史」里能查到
2. **稿件的 AI 判断**（设计 5.5.1）：`moderation/panels.py` 的 `ModerationVerdictPanel` 放在文章编辑页最上面（「AI 审核」）：风险、类别、理由、引用原文、链到复核详情；还没审完写「AI 还在看」；没有记录不显示；只有能复核内容的人看到
3. **排版设置**（设计 13.12）：表单和预览包进 `typography-layout`，宽屏（≥ 75em）两栏，预览在右边并 `position: sticky` 停在视野里；窄屏照旧上下
4. **赛事人数下限**：`TournamentAdminForm` 在下限或报名方式改动（或新建）时检查，整队报名时下限超过全站战队人数上限就在这一栏报错；这一栏的说明写出当前上限；`roster_min_warning` 对个人报名的赛事不再提示（临时队伍不受战队人数上限约束）。全站上限之后调低、旧赛事这一栏没动时，不挡别的修改，保存后照旧提示
5. **逐行查询**：用户功能规则、用户组功能限制列表 `select_related`；队伍编排页新函数 `registration.pool_conflicts()` 一次查出整个散人池谁已在别的名单里（文字和原来一样，共用 `_roster_conflict_message`）；「我的投稿」用 Wagtail 的 `prefetch_workflow_states()`
6. **写法统一**（#29）：新片段 `core/admin/_tabs.html`（状态按钮，当前的带 `aria-current`）和 `core/admin/_pager.html`（翻页，用 Django 的 `{% querystring %}` 保留筛选），内容审核、头像审核、报名审核、静态页面、分队页的排序都换成它们
7. **文档**：设计 v6.15（14.4、5.5.1、8.1 字段表、12.11 约束表，附录 D）

## 命令输出

（见下面各节，均为本机实际运行。）

变异（`mutate.py`，24 处，第一次全部被抓到）：

```
baseline green, 13 tests
caught publishing a tournament is not logged -> test_tournament_buttons_are_on_record
caught cancelling a tournament is not logged -> test_tournament_buttons_are_on_record
caught the log actions have no labels -> test_tournament_buttons_are_on_record
caught publishing a scrim is not logged -> test_scrim_buttons_and_the_split_page_are_on_record
caught cancelling a scrim is not logged -> test_scrim_buttons_and_the_split_page_are_on_record
caught saving who plays is not logged -> test_scrim_buttons_and_the_split_page_are_on_record
caught saving the split is not logged -> test_scrim_buttons_and_the_split_page_are_on_record
caught assigning a captain is not logged -> test_team_rescue_actions_are_on_record
caught disbanding is not logged -> test_team_rescue_actions_are_on_record
caught saving the board is not logged -> test_saving_the_arrangement_board_is_on_record
caught the editor shows no AI read -> test_editors_see_the_ai_read_on_a_submission
caught submitters see the AI read -> test_editors_see_the_ai_read_on_a_submission
caught an unfinished review shows as a verdict -> test_a_submission_still_under_review_says_so
caught the preview goes back under the form -> test_the_typography_preview_sits_beside_the_form
caught the preview scrolls away -> test_the_typography_preview_sits_beside_the_form
caught the minimum is only checked after saving -> test_a_team_minimum_above_the_site_cap_is_refused_before_saving
caught the field does not say the cap -> test_a_team_minimum_above_the_site_cap_is_refused_before_saving
caught individual tournaments are capped too -> test_a_team_minimum_above_the_site_cap_is_refused_before_saving
caught user rules query per row -> test_feature_rule_lists_do_not_query_per_row
caught group rules query per row -> test_feature_rule_lists_do_not_query_per_row
caught the board asks once per person -> test_the_arrangement_board_does_not_query_per_person
caught my submissions query per article -> test_my_submissions_do_not_query_per_article
caught page links drop the filters -> test_page_links_keep_the_filters
caught the review list writes its own pager -> test_custom_admin_lists_share_the_tabs_and_the_pager
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
293 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1425 passed in 180.15s (0:03:00)
```

本机截图（超级管理员，1440 宽）：排版设置左边是九个区域的表单，右边是「实时预览」。

演示站（镜像时间 `2026-10-03 17:44:37 +0200`）：

```
  No migrations to apply.
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
发布赛事 处理待复核内容
```

（最后一行是在服务器上查操作记录的动作名；第一次查忘了先让 Wagtail 扫描钩子，报了 `KeyError`，补上 `registry.scan_for_actions()` 后正常。网页上 Wagtail 会自己扫描。）

## 没做 / 未验证

- 前台队长的操作（解散、转让）不进 Wagtail 操作记录（见复核「最没把握的」第 1 条）
- 演示站后台要配好 HTTPS 才能登录，编辑页的「AI 审核」一块没在演示站上看过（本机测试覆盖）
- 排版设置预览的「停在视野里」靠 `position: sticky`，整页截图看不出效果，没在真浏览器里滚动看
