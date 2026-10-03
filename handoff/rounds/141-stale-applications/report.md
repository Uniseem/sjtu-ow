# 141 队长 14 天没处理的入队申请自动关闭（报告）

## 做了什么

1. `teams/services.py`：`STALE_APPLICATION_DAYS`、`STALE_NOTE`、`stale_applications()`、`close_stale_applications()`
2. `teams/notifications.py`：`application_expired_letter()` / `application_expired()`
3. `core/management/commands/cleanup_old_data.py`：最后关闭过期申请，单独一行「将关闭 / 已关闭 …（并通知申请人）：N」
4. 设计 v6.36（7.3 状态表、10.2），README 战队一节和定时维护一节
5. `teams/tests/test_stale_applications.py`（3 条）

## 两处修正

- 测试「已经处理过的旧申请不动」第一版先把申请改到 30 天前再拒绝，拒绝时整条记录重存，提交时间又回到了现在，测试其实没测到旧申请；变异漏了这一处。改成拒绝之后再改时间，重跑抓到
- 第一版的命令输出沿用「将删除 / 已删除」前缀，部署后在演示站试运行时看到不对（申请是关闭，不是删除），改成单独一行

## 命令输出

变异（测试机，6 处，修正测试后全部被抓到）：

```
baseline green, 3 tests
caught closed after twelve days -> test_two_weeks_unanswered_closes_and_tells_the_applicant
caught answered ones are closed too -> test_answered_ones_are_left_alone
caught nobody is told -> test_two_weeks_unanswered_closes_and_tells_the_applicant
caught no reason recorded -> test_two_weeks_unanswered_closes_and_tells_the_applicant
caught the nightly job skips it -> test_two_weeks_unanswered_closes_and_tells_the_applicant
caught a dry run closes them -> test_a_dry_run_only_counts
restored and green; missed: none
```

整组检查（测试机）：

```
1556 条测试分成 4 片
分片 1：389 passed in 34.49s
分片 2：389 passed in 39.05s
分片 3：389 passed in 34.09s
分片 4：389 passed in 33.93s
== 迁移 (21:37:22)
No changes detected
== 生产配置 (21:37:23)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:37:24)
== Docker 镜像 (21:37:25)
构建成功：988243eed83c
== 全部通过 (21:37:25)
```

演示站升级后试运行：

```
将删除 已完成的任务记录（30 天前）：0
将删除 已处理的 AI 审核记录（180 天前）：0
将删除 过期会话：0
将关闭 14 天没人处理的入队申请（并通知申请人）：0
```

## 没做 / 未验证

- 演示站上没有超过 14 天的待审批申请，夜里真跑时没有可关的
