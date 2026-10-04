# 162 后台「活动数据」（报告）

## 做了什么

1. `core/activity.py`（新）：`Period`（起止日期，含两头，按北京时间换成时刻）、`school_year()` / `last_school_year()` / `recent()`、`period_from()`（日期不对回到本学年并说明）、`events()`（逐场：内战的报名人次和上场人次，赛事的通过队伍和参赛人数）、`summary()`、`csv_text()`（带 BOM）、`can_view()`、`activity_view()`
2. `core/templates/core/admin/activity.html`（新）：快捷时间段、起止日期、汇总表、逐场表、下载 CSV
3. `core/wagtail_hooks.py`：地址 `/admin/activity/`、「社区」下的菜单项（只给能看的人）
4. 后台手册站长部分加一步；设计 v6.53（14.1 菜单表、14.2）；README「活动数据」
5. `scripts/screens.py`：种子数据加一个超级管理员「截图站长」，可以截后台页面；加了 `admin-activity`
6. `core/tests/test_activity.py`（4 条）；`core/tests/test_admin_wording.py` 的菜单顺序加上「活动数据」

## 口径

- 只数已发布和已结束的内战、赛事；草稿、已取消的不算
- 内战按开始时间；赛事按比赛时间，没填按报名截止时间
- 内战：报名人次（全部报名）、上场人次（勾了上场的）、参与人数（这段时间报过名的人，去重）
- 赛事：通过的队伍、参赛人数（已通过名单里占名额的人，去重）
- 新成员：注册时间在段内、在用、验证过邮箱（和成员展示一样）
- 文章：段内首次发布、现在在线；评论：段内发的，不算隐藏和作者删除的

## 已有测试拦下的

第一次整组检查 `test_the_menu_follows_the_design_order` 红了：「社区」子菜单的顺序是按设计 14.1 的表钉死的，新菜单项没写进表。设计 14.1 加一行，测试的期望加上「活动数据」。

## 写测试时改的

- 第一版测试里 `_article` 调了两次，没有超级管理员时它每次都建同一个作者，邮箱重复。夹具里先建一个超级管理员（没有验证邮箱，不算成员）
- 数逐场的行时 `data-activity-event` 也匹配到了表格上的 `data-activity-events`，改成数 `<tr data-activity-event>`
- 写变异前补了两处：同一个人打两项赛事（否则「参赛人数不去重」改坏了也不红）；9 月 1 日当天算新学年

## 命令输出

变异（测试机，21 处，全部被抓到）：

```
baseline green, 4 tests
caught cancelled scrims count -> test_the_months_numbers
caught the next day's midnight counts -> test_the_months_numbers
caught the last day is cut off -> test_the_months_numbers
caught undated tournaments vanish -> test_the_months_numbers
caught cancelled tournaments count -> test_the_months_numbers
caught rejected rosters play -> test_the_months_numbers
caught everyone signed up played -> test_the_months_numbers
caught rejected teams count -> test_the_months_numbers
caught scrim people counted twice -> test_the_months_numbers
caught tournament people counted twice -> test_the_months_numbers
caught hidden comments count -> test_the_months_numbers
caught deleted comments count -> test_the_months_numbers
caught everyone is from SJTU -> test_the_months_numbers
caught old articles count -> test_the_months_numbers
caught old teams count -> test_the_months_numbers
caught 1 September belongs to the year before -> test_the_periods
caught thirty-one days -> test_the_periods
caught backwards periods pass -> test_the_periods
caught scrim managers shut out -> test_officers_see_it_and_can_take_the_table_away
caught no BOM -> test_officers_see_it_and_can_take_the_table_away
caught menu for everyone -> test_writers_do_not
restored and green; missed: none
```

整组检查（测试机，补了菜单表之后）：

```
1610 条测试分成 4 片
分片 1：403 passed in 38.57s
分片 2：403 passed in 39.90s
分片 3：402 passed in 38.60s
分片 4：402 passed in 38.28s
== 全部通过 (02:02:36)
```

截图（测试机，1280 宽，超级管理员）：页面在 Wagtail 后台里正常显示，快捷按钮、起止日期、汇总表都在；截图用的种子数据里内战和赛事都在将来，所以「逐场」是「这段时间没有内战和赛事」。起止日期的输入框是 Wagtail 默认的整行宽，能用，没改。

演示站升级后，在服务器上用演示数据算（服务层直接算，再以演示站的内战管理员「老周」用测试客户端打开页面和 CSV）：

```
本学年 2026-09-01 2026-10-04 {'members': 0, 'sjtu_members': 0, 'scrims': 2, 'scrim_signups': 22, 'scrim_players': 10, 'scrim_people': 20, 'tournaments': 0, 'tournament_teams': 0, 'tournament_people': 0, 'articles': 18, 'comments': 62, 'teams': 1}
   09-18 内战 周五夜内战 已结束 12 10
   09-25 内战 中秋内战 已结束 10 0
上学年 2025-09-01 2026-08-31 {'members': 13, 'sjtu_members': 11, 'scrims': 0, 'scrim_signups': 0, 'scrim_players': 0, 'scrim_people': 0, 'tournaments': 1, 'tournament_teams': 4, 'tournament_people': 23, 'articles': 3, 'comments': 8, 'teams': 2}
   04-12 赛事 2026 春季校内杯 已结束 4 23
老周打开: 200 行数: 2
CSV: 200 text/csv; charset=utf-8 True
```

## 没做 / 未验证

- 没在浏览器里点过（演示站还没有能登录后台的账号）
- 没按学期分（9 月到 1 月、2 月到 7 月）：各校学期日期不一样，用自定义起止日期就能查
