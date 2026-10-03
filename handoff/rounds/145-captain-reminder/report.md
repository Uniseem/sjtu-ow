# 145 入队申请等了 7 天提醒队长一次（报告）

## 做了什么

1. `teams/models.py`：`TeamApplication.captain_reminded_at`（迁移 teams/0005）
2. `teams/services.py`：`REMIND_CAPTAIN_DAYS`、`remind_captains()`（按战队分组，未解散的战队，一封信，记时间）
3. `teams/notifications.py`：`applications_waiting_letter()` / `applications_waiting()`
4. `core/management/commands/cleanup_old_data.py`：关闭之后提醒，输出「已提醒队长（入队申请等了 7 天）：N 封」；`--dry-run` 不提醒
5. 邮件样张「入队申请等你处理」
6. 设计 v6.39，README 战队、定时维护两节
7. `teams/tests/test_stale_applications.py` 加 3 条

## 命令输出

变异（测试机，7 处，第一次全部被抓到）：

```
baseline green, 2 tests
caught the nightly job does not remind -> test_a_week_in_the_captain_hears_once
caught reminded after three days -> test_a_week_in_the_captain_hears_once
caught reminded every night -> test_a_week_in_the_captain_hears_once
caught nothing marked as reminded -> test_a_week_in_the_captain_hears_once
caught one letter per application -> test_a_week_in_the_captain_hears_once
caught no word about closing -> test_a_week_in_the_captain_hears_once
caught no specimen -> test_the_reminder_is_on_the_specimen_page
restored and green; missed: none
```

整组检查（测试机）：

```
1571 条测试分成 4 片
分片 1：393 passed in 36.52s
分片 2：393 passed in 35.62s
分片 3：393 passed in 35.96s
分片 4：392 passed in 35.46s
== 迁移 (22:11:43)
No changes detected
== 生产配置 (22:11:44)
System check identified no issues (0 silenced).
== 错误页和模板一致 (22:11:45)
== Docker 镜像 (22:11:46)
构建成功：183b86dbe846
== 全部通过 (22:11:46)
```

演示站升级：

```
  Applying teams.0005_captain_reminded_at... OK
 [X] 0005_captain_reminded_at
```

## 没做 / 未验证

- 试运行（`--dry-run`）不统计会提醒几封
- 已经存在的、超过 7 天的申请，第一次夜里跑时都会提醒（演示站上没有）
