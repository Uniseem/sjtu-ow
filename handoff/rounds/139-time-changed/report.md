# 139 改了比赛时间要告诉报了名的人（报告）

## 做了什么

1. `tournaments/services.time_changed(tournament, old)`：条件满足时清掉 `reminder_sent_at`，事务提交后发信，返回是否算改期
2. `tournaments/notifications.py`：`time_changed_letter()`（开头一句「原来 X，现在 Y」，下面「现在的时间」和选手联系方式）、`participants()`（占名额的名单行和个人报名的人，去重，账号在用且有邮箱）、`time_changed()`
3. `tournaments/wagtail_hooks.TournamentSaveMixin`：保存前从 `form.initial` 取原来的时间，保存后先 `time_changed()` 再 `after_change()`（后者按清掉的标记重新安排提醒）
4. 内战同样：`scrims/services.time_changed()`、`scrims/notifications.scrim_time_changed_letter()` / `scrim_time_changed()`、`ScrimSaveMixin`
5. 邮件样张「比赛时间改了」「内战时间改了」
6. 设计 v6.34，README 赛事和内战两节
7. 测试：`tournaments/tests/test_time_changed.py`（5 条）、`scrims/tests/test_time_changed.py`（3 条）；后台编辑页的测试用 `querydict_from_html` 照页面上的表单提交

## 命令输出

变异（测试机，12 处）。第一次漏了「信里不写原来的时间」两处：原来的时间在开头那句和事实列表里各写了一遍，删掉一个测试照样绿。去掉了事实列表里重复的那一行，变异改成改坏开头那句，重跑全部被抓到：

```
baseline green, 8 tests
caught tournament admin save says nothing -> test_saving_in_the_admin_sends_it
caught tournament: drafts tell people -> test_nothing_said_when_nothing_moved
caught tournament: an unchanged time tells people -> test_nothing_said_when_nothing_moved
caught tournament: moving into the past tells people -> test_nothing_said_when_nothing_moved
caught tournament: the old reminder still counts -> test_the_people_taking_part_hear_from_when_to_when
caught tournament: the pool is left out -> test_the_pool_hears_too
caught tournament: rejected rosters hear -> test_a_rejected_roster_does_not_hear
caught tournament: the old time is not said -> test_the_people_taking_part_hear_from_when_to_when
caught scrim admin save says nothing -> test_saving_in_the_admin_sends_it
caught scrim: drafts tell people -> test_nothing_said_when_nothing_moved
caught scrim: the old reminder still counts -> test_everyone_signed_up_hears
caught scrim: the old time is not said -> test_everyone_signed_up_hears
restored and green; missed: none
```

整组检查（测试机）：

```
1550 条测试分成 4 片
分片 1：388 passed in 37.30s
分片 2：388 passed in 40.00s
分片 3：387 passed in 38.79s
分片 4：387 passed in 38.13s
== 迁移 (21:16:14)
No changes detected
== 生产配置 (21:16:15)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:16:16)
== Docker 镜像 (21:16:17)
构建成功：660a7d7f4c76
== 全部通过 (21:16:17)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 内战的「时间没变 / 改到过去」两个条件没有单独的变异（和赛事那两条写法一样，赛事那边逐条改坏过）
- 管理员一天里来回改几次时间，每次都会发一封
