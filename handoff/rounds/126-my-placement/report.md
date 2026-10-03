# 126 内战参加者能看到自己的分队（报告）

## 做了什么

1. `scrims/services.py`：`split_scrim_ids()`（哪些内战已经有人分进 A/B 队，一次查询）、`placement()`
2. 活动页报名区：`actions_context` 加 `my_placement`，模板在「已报名」那行下面写「当前分队：A 队 · 坦克（以管理员在群里发的为准）」
3. 「我的内战」：视图把列表一次查出分队情况，表格加「分队」列，没分队写「还没分队」
4. 提醒邮件：`scrim_reminder()` 改成每个报名者一封（停用、没邮箱的跳过，和原来一样），`scrim_reminder_letter(scrim, placement)` 有分队时加一行「你的分队」
5. 设计 v6.22（9.2）

## 命令输出

变异（`mutate.py`，6 处，第一次全部被抓到）：

```
baseline green, 4 tests
caught a place before any split -> test_the_wording_for_each_place
caught a place before any split -> test_my_scrims_lists_my_place
caught open formats name a role -> test_the_wording_for_each_place
caught the bench reads as left out -> test_the_wording_for_each_place
caught the scrim page hides my place -> test_the_scrim_page_shows_only_my_place
caught my scrims shows no place -> test_my_scrims_lists_my_place
caught the reminder leaves out the place -> test_the_reminder_tells_each_player_their_place
restored and green; missed: none
```

整组检查：

```
All checks passed!
303 files already formatted
Built production stylesheet 'D:\claude\sjtu-ow\static\css\app.css'.
No changes detected
System check identified no issues (0 silenced).
1479 passed in 308.98s (0:05:08)
```

演示站已升级。

## 没做 / 未验证

- 管理员保存分队后不另外通知报名者（结果照旧由管理员发群）；分队可能临开始前还在调，邮件只在提醒时带上当时的结果
