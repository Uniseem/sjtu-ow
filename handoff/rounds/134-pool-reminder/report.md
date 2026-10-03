# 134 没编进队伍的散人也收到开赛提醒（报告）

## 做了什么

1. `tournaments/notifications.py`：`unplaced_reminder_letter()`、`unplaced_reminder()`（`registration` 为空的个人报名，账号在用且有邮箱）
2. `tournaments/tasks.py`：队伍提醒一封都没发出时直接返回 `sent:0`（不记为已发送，散人也不发）；发出了才给散人发，返回 `sent:N,pool:M`（没有散人信时仍是 `sent:N`，129 的测试不用改）
3. `tournaments/notifications_registration.py`：「已编入临时队伍」有比赛时间就写
4. 邮件样张页「赛事开始提醒（还没编进队伍）」
5. 设计 v6.29（8.1、10.2），README 赛事一节
6. `tournaments/tests/test_reminder.py` 加 5 条

## 命令输出

变异（测试机，6 处，第一次全部被抓到）：

```
baseline green, 5 tests
caught the pool hears nothing -> test_the_pool_hears_once_teams_are_being_formed
caught the pool hears before any team exists -> test_no_teams_yet_no_pool_letters
caught placed players get the pool letter too -> test_the_pool_hears_once_teams_are_being_formed
caught deactivated pool signups hear too -> test_a_deactivated_pool_signup_is_skipped
caught being placed says nothing about when -> test_being_placed_says_when
caught no specimen -> test_the_pool_letter_is_on_the_specimen_page
restored and green; missed: none
```

整组检查（测试机）：

```
1520 条测试分成 4 片
分片 1：380 passed in 31.65s
分片 2：380 passed in 32.76s
分片 3：380 passed in 31.58s
分片 4：380 passed in 32.09s
== 迁移 (20:35:29)
No changes detected
== 生产配置 (20:35:30)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:35:31)
== Docker 镜像 (20:35:32)
构建成功：713bc3e2720f
== 全部通过 (20:35:32)
```

演示站已升级（没有迁移）。

## 没做 / 未验证

- 129 的 `mutate.py` 里「marked sent with nobody to tell」那一处的目标代码这轮改了写法，旧脚本那一条已经对不上（轮次脚本不改）；同样的规则现在由 `test_only_approved_rosters_hear` 和 `test_no_teams_yet_no_pool_letters` 守着，本轮「the pool hears before any team exists」改坏后也会红
