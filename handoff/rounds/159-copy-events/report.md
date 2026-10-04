# 159 内战、赛事可以「复制」成新的一场（报告）

## 做了什么

1. `core.services.weeks_ahead()`：要挪几整周，最早的时间才在将来，至少 1；`copy_ahead()`：新建一个没保存的对象，只放列出的字段和挪过的时间
2. `scrims.services`、`tournaments.services`：`COPIED_FIELDS`、`COPIED_TIMES`（就是表单里的全部字段）、`copy_for_new()`
3. 两个后台：去掉 `copy_view_enabled = False`；`ScrimCopyView`、`TournamentCopyView` = Wagtail 的 `CopyViewMixin` + 本站的新建页（保存时同样记创建人、排提醒、刷新页面），预填用 `copy_for_new()`
4. 后台手册：内战管理员、赛事管理员各加一句
5. 设计 v6.51（14.2）；README「赛事」「内战」
6. `core/tests/test_copy_events.py`（5 条）

## 写测试时发现并改掉的

1. 第一版照 Wagtail 自带的复制页，拿原来那条记录预填、只改时间和清主键。测试把表单直接提交回复制地址时，新建的那条带着原来的「已发布」「已结束」和发布时间：等于绕过发布流程多出一场已发布的。改成 `copy_ahead()` 只照抄列出的字段、新建对象。加了一条测试：表单字段必须等于「照抄 + 挪时间」两张表，以后表单加字段、没在这里决定的话会红
2. 变异「复制页不走本站的保存步骤」第一次漏了：正常提交去的是新建地址，复制页自己的保存只有直接提交回复制地址时才会走。测试补上对这一条的检查（草稿、创建人）后抓到
3. 测试工具读勾选框时把没写 value 的勾选框读成空字符串，Django 会当成没勾；浏览器发的是 `on`。测试里按 HTML 的 `checked` 改回 `on`。文本框开头的换行（Django 在 `<textarea>` 后面加的，浏览器会忽略）比较时去掉

## 命令输出

变异（测试机，15 处，全部被抓到）：

```
baseline green, 5 tests
caught today counts as ahead -> test_how_far_a_copy_moves
caught one week short -> test_how_far_a_copy_moves
caught one week short -> test_last_years_tournament_lands_this_year
caught blank times trip it -> test_how_far_a_copy_moves
caught times stay where they were -> test_a_weekly_scrim_is_copied_to_next_week
caught times stay where they were -> test_last_years_tournament_lands_this_year
caught copy starts from the old row -> test_a_weekly_scrim_is_copied_to_next_week
caught copy starts from the old row -> test_last_years_tournament_lands_this_year
caught scrim close time not moved -> test_a_weekly_scrim_is_copied_to_next_week
caught scrim close time not moved -> test_every_form_field_is_copied_or_moved
caught scrim rule left blank -> test_a_weekly_scrim_is_copied_to_next_week
caught scrim rule left blank -> test_every_form_field_is_copied_or_moved
caught tournament contact left blank -> test_last_years_tournament_lands_this_year
caught tournament contact left blank -> test_every_form_field_is_copied_or_moved
caught tournament status copied too -> test_last_years_tournament_lands_this_year
caught tournament status copied too -> test_every_form_field_is_copied_or_moved
caught scrim copy turned off again -> test_a_weekly_scrim_is_copied_to_next_week
caught scrim copy turned off again -> test_copy_is_in_the_menu_for_those_who_may_add
caught scrim copy is Wagtail's plain one -> test_a_weekly_scrim_is_copied_to_next_week
caught scrim copy skips the save steps -> test_a_weekly_scrim_is_copied_to_next_week
caught tournament copy skips the save steps -> test_last_years_tournament_lands_this_year
caught tournament copy is Wagtail's plain one -> test_last_years_tournament_lands_this_year
caught the manual does not say -> test_copy_is_in_the_menu_for_those_who_may_add
restored and green; missed: none
```

整组检查（测试机）：

```
1604 条测试分成 4 片
分片 1：401 passed in 35.71s
分片 2：401 passed in 38.01s
分片 3：401 passed in 38.33s
分片 4：401 passed in 37.41s
== 迁移 (01:24:43)
No changes detected
== 生产配置 (01:24:44)
System check identified no issues (0 silenced).
== 错误页和模板一致 (01:24:45)
== Docker 镜像 (01:24:46)
构建成功：45490881c469
== 全部通过 (01:24:46)
```

演示站升级后，在服务器上用 Django 的测试客户端以演示站的内战管理员「老周」（`force_login`，不用密码）打开复制页，只看不提交：

```
列表里有复制: True
复制页: 200
原来: 周日下午 · 新人友好场 2026-10-11 07:00:00+00:00 2026-10-11 05:00:00+00:00
title = 周日下午 · 新人友好场
starts_at = 2026-10-18 15:00
signup_closes_at = 2026-10-18 13:00
format = open_5v5
提交到: /admin/scrims/new/
内战总数没变: 7
```

原来那场是北京时间 10-11 15:00（还没开始），复制出来是下一周同一时间。

## 没做 / 未验证

- 没在浏览器里点过「复制」再保存（演示站没有能登录后台的账号；HTTPS 下的后台由用户自己的账号登录）。保存这一步只在测试里验证
- 隔周、每月的活动挪完要自己再改日期
