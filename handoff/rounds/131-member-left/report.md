# 131 队员退出战队时告诉队长（报告）

## 做了什么

1. `tournaments/registration.py`：`entries_still_listing(team, user)`，战队的报名里，赛事是草稿或已发布、这个人的名单行还占名额的，按报名截止时间排
2. `teams/notifications.py`：`member_left_letter()`、`member_left()`（没有队长就不发）
3. `teams/services.leave_team()`：退出后发信
4. 邮件样张页加「队员退出战队」；样张赛事补了报名截止时间
5. 设计 v6.26：7.4 表、10.2、10.3，头部版本号
6. README 战队一节

## 一处改动的理由

`entries_still_listing` 一开始也按报名状态过滤（待审核、已通过）。变异时去掉这个条件测试没红：名单行的「占名额」由 `_set_status` 跟着报名状态一起改（`registration.members.update(is_active=to_status in ACTIVE_STATUSES)`），两个条件重复。留下「占名额」这一个（它还能排除同步名单时被换下的人），加了注释，变异改去掉这个条件，会红。

## 命令输出

变异（测试机，6 处；第一次漏了上面那一处，改完代码后重跑全部被抓到）：

```
baseline green, 4 tests
caught leaving tells nobody -> test_the_captain_hears_who_left
caught rejected rosters are named -> test_dead_registrations_are_not_named
caught finished tournaments are named -> test_dead_registrations_are_not_named
caught the letter leaves out the roster -> test_a_live_roster_that_still_lists_them_is_named
caught the letter points to the team, not the entry -> test_a_live_roster_that_still_lists_them_is_named
caught no specimen -> test_the_letter_is_on_the_specimen_page
restored and green; missed: none
```

第一次的输出：

```
MISSED rejected rosters are named -> test_dead_registrations_are_not_named
```

整组检查（测试机）：

```
1506 条测试分成 4 片
分片 1：377 passed in 32.17s
分片 2：377 passed in 35.56s
分片 3：376 passed in 33.99s
分片 4：376 passed in 33.42s
== 迁移 (20:11:14)
No changes detected
== 生产配置 (20:11:15)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:11:16)
== Docker 镜像 (20:11:17)
构建成功：d47ab22f1404
== 全部通过 (20:11:17)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 演示站没配 SMTP，信发不出去
- 「已结束的赛事不点名」的测试是把另一场赛事的报名改挂到这支战队上造出来的，不是从界面走出来的
