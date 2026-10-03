# 135 内战开始 6 小时后自动标记已结束（报告）

## 做了什么

1. `scrims/services.py`：`FINISH_AFTER`（6 小时）、`finish_time()`、`schedule_auto_finish()`；`publish()` 和 `after_change()`（已发布时）里安排
2. `scrims/tasks.py`：`finish_past_scrim`，没了 / 不是已发布就返回，不到点改期，到点调 `services.finish()`
3. `scrims/tests/test_auto_finish.py`（4 条）
4. 设计 v6.30（9.1、默认值表），README 内战一节

## 演示站

升级后给已发布的内战补安排（升级前发布的要保存一次才会安排，这里用脚本直接排）：

```
2 国庆特别场 · 6v6 怀旧 2026-10-05 19:30:00+08:00 结束于 2026-10-06 01:30:00+08:00
3 周三内战 2026-10-07 20:00:00+08:00 结束于 2026-10-08 02:00:00+08:00
1 周五夜内战 2026-10-09 20:00:00+08:00 结束于 2026-10-10 02:00:00+08:00
7 周日下午 · 新人友好场 2026-10-11 15:00:00+08:00 结束于 2026-10-11 21:00:00+08:00
[(4, 'finished'), (5, 'finished'), (2, 'published'), (3, 'published'), (1, 'published'), (7, 'published'), (6, 'draft')]
```

（都还没开始，所以都还是「已发布」）

## 命令输出

变异（测试机，7 处，第一次全部被抓到）：

```
baseline green, 4 tests
caught publishing arranges nothing -> test_publishing_and_saving_arrange_it
caught saving does not follow the new start -> test_publishing_and_saving_arrange_it
caught a draft edit arranges it too -> test_a_draft_edit_arranges_nothing
caught an hour, not six -> test_too_early_or_cancelled_leaves_it_alone
caught finished early -> test_too_early_or_cancelled_leaves_it_alone
caught cancelled scrims get finished -> test_too_early_or_cancelled_leaves_it_alone
caught the task never finishes it -> test_six_hours_after_the_start_it_is_finished
restored and green; missed: none
```

整组检查（测试机）：

```
1524 条测试分成 4 片
分片 1：381 passed in 32.37s
分片 2：381 passed in 34.53s
分片 3：381 passed in 31.48s
分片 4：381 passed in 30.96s
== 迁移 (20:41:55)
No changes detected
== 生产配置 (20:41:56)
System check identified no issues (0 silenced).
== 错误页和模板一致 (20:41:57)
== Docker 镜像 (20:41:58)
构建成功：3a6453be1eae
== 全部通过 (20:41:58)
```

## 没做 / 未验证

- 自动结束不写后台操作日志（手动点的按钮写，119 起）：系统做的，没有操作人
- 没等到演示站上真的有一场到点（最早的是 10-06 01:30）
