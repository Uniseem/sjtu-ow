# 118 后台的功能（报告）

## 做了什么

1. **后台首页的「待办」**（#24）：新模块 `core/admin_todo.py`，首页最上面一块（`construct_homepage_panels` 插在最前）。每行是一句话加链接，数量为零的不列，全为零写「暂时没有待办」：
   - 能复核内容的人（内容编辑、超管）：待复核的内容（和列表默认条件一致：待复核、已审完、风险不是「无」）、待审核的头像
   - 等他审的稿件：Wagtail 工作流里进行中的步骤，审批组和他的组有交集的（超管全部），链到 Wagtail 的工作流报告
   - 能管赛事的人：待审核的报名（不含已取消的赛事），每项已发布赛事里等待编队的人数，链到那项赛事的编排页
   - 能管内战的人：已发布、报名已截止、还没开始、没有一个人被分进 A/B 队的内战，链到分队页
   - 超管：生成失败的静态页面，链到筛好「生成失败」的列表
   - 不管这些队列的人（比如认证作者）不显示这块（`has_duties`）；纯投稿者照旧只看「我的投稿」
2. **内容审核**（#21）：
   - 列表加「提交时间」筛选（最近 24 小时、7 天、30 天），翻页带上筛选
   - 「全量扫描」按钮（先确认）：`moderation.integrations.scan_existing()` 把在用账号的昵称和个人宣言、已发布的文章和普通页面、没解散的战队的队名和简介、没隐藏没删除的评论送审（原来的命令只扫昵称、宣言和页面，现在命令也调这个函数）。按设计 5.5.3 排到 DeepSeek 的低价时段（北京时间 0:30–8:30），白天点就排到当天夜里 0:30（`scan_start`）；用缓存锁保证同一时间只排一次，任务跑完解锁；按钮在扫描排上或进行中时置灰
   - 每次处理写一条 Wagtail 操作记录（`moderation.handle`，含结果和说明），详情页新增「处理记录」表列出全部
   - 「直接处置」没做，等你定（复查第五部分）
3. **内战分队页**（#25）：
   - 排序换成两个按钮，当前的高亮（`aria-current`）；两个表单都带上排序，保存后回到同一个排序
   - 「复制」按钮：`navigator.clipboard`，浏览器不让复制（非 HTTPS 等）时选中文本、提示按 Ctrl+C
   - 有联系方式权限的人（`accounts.view_contactmethod`，设计 4.1 给赛事管理员和内战管理员）在报名表里多一列联系方式
4. **「账号已停用」**（3.7）：报名审核列表（名单里有几个停用账号，`Count` 注解）、报名详情的名单、队伍编排页的卡片、内战分队页的报名表和分队卡片
5. **文档**：设计 v6.14（14.1 加「后台首页」、14.2 内容审核和内战活动两行、5.5.4 三处）；README（命令立即执行、按钮排到夜间）

## 命令输出

（见下面各节，均为本机实际运行。）

变异（`mutate.py`，29 处，第一次全部被抓到）：

```
baseline green, 18 tests
caught the dashboard has no to-do panel -> test_content_editors_see_what_waits_for_review
caught reviewers get no review rows -> test_content_editors_see_what_waits_for_review
caught avatars counted by the wrong status -> test_content_editors_see_what_waits_for_review
caught submissions counted for nobody -> test_editors_see_submissions_waiting_for_them
caught tournament managers get no rows -> test_tournament_managers_see_registrations_and_the_pool
caught the pool counts placed people -> test_tournament_managers_see_registrations_and_the_pool
caught split scrims stay on the list -> test_scrim_managers_see_closed_scrims_without_teams
caught superusers miss failed pages -> test_superusers_see_failed_static_pages
caught empty rows are listed -> test_nothing_waiting_says_so_and_people_without_queues_get_no_panel
caught everyone gets the panel -> test_nothing_waiting_says_so_and_people_without_queues_get_no_panel
caught the review list ignores the time filter -> test_the_review_list_filters_by_time
caught two scans at once -> test_the_full_scan_runs_in_the_background_once_at_a_time
caught the scan runs at peak prices -> test_the_full_scan_waits_for_the_off_peak_hours
caught the scan keeps its lock -> test_the_scan_task_releases_its_lock
caught the scan skips teams -> test_the_scan_covers_teams_and_comments_too
caught the scan skips comments -> test_the_scan_covers_teams_and_comments_too
caught handling is not logged -> test_every_handling_stays_on_record
caught saving drops the order -> test_the_split_page_keeps_its_order_after_saving
caught the current order is not marked -> test_the_split_page_keeps_its_order_after_saving
caught managers see no contacts -> test_scrim_managers_see_contacts_on_the_split_page
caught everyone sees contacts -> test_scrim_managers_see_contacts_on_the_split_page
caught no copy button -> test_the_split_result_has_a_copy_button
caught the copy button copies nothing -> test_the_split_result_has_a_copy_button
caught the split table hides deactivation -> test_split_page_marks_deactivated_accounts
caught split cards hide deactivation -> test_split_page_marks_deactivated_accounts
caught the review list hides deactivation -> test_registration_review_marks_deactivated_accounts
caught the review list counts nobody -> test_registration_review_marks_deactivated_accounts
caught the roster hides deactivation -> test_registration_review_marks_deactivated_accounts
caught the board hides deactivation -> test_the_arrangement_board_marks_deactivated_accounts
restored and green; missed: none
```

整组检查（开发服务器停着）：

```
All checks passed!
290 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1412 passed in 348.57s (0:05:48)
```

本机截图（超级管理员，1440 宽）：首页「待办」两行（「2 份报名等待审核」「「2026 新生杯」有 1 人等待编队」）；内容审核多了「提交时间」筛选和「全量扫描」按钮（本机 AI 审核关着，按钮置灰）；分队页「按段位」高亮、报名表有联系方式一列。

演示站（镜像时间 `2026-10-03 17:21:55 +0200`）：

```
  No migrations to apply.
全量生成完成：成功 46，失败 0，删除 0；目录占用 1604 KB
{"status": "ok", ...}
['2 份报名等待审核', '「2026 新生杯」有 1 人等待编队']
2026-10-04 00:30:00+08:00
```

（后两行是在服务器上以未保存的超管对象算待办、算此刻点「全量扫描」的开始时间。）

## 没做 / 未验证

- 内容审核的「直接处置」（等用户定）
- 演示站后台要配好 HTTPS 才能登录，后台页面没有在演示站上截图（本机截过）
- 「复制」按钮在真浏览器里点击没有测（无头截图不点击）；脚本逻辑由测试读源码检查，剪贴板接口要求 HTTPS，`http://IP:22887` 上会退回「选中文本」
