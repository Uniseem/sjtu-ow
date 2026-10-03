# 142 后台待办提醒赛事管理员标记结束（报告）

## 做了什么

1. `core/admin_todo.py`：`FINISH_NUDGE_AFTER`（3 天）；`_tournament_rows()` 末尾每场一行
2. `core/tests/test_admin_functions.py` 加 1 条
3. 删 `moderation/views.py`；`tournaments/services.py` 模块注释
4. 设计 v6.37（14.1）

## 命令输出

变异（测试机，3 处，第一次全部被抓到）：

```
baseline green, 1 tests
caught no nudge at all -> test_tournaments_long_started_ask_to_be_finished
caught nudged the day after -> test_tournaments_long_started_ask_to_be_finished
caught finished ones nudged too -> test_tournaments_long_started_ask_to_be_finished
restored and green; missed: none
```

整组检查（测试机）：

```
1557 条测试分成 4 片
分片 1：390 passed in 33.18s
分片 2：389 passed in 35.41s
分片 3：389 passed in 36.64s
分片 4：389 passed in 33.44s
== 迁移 (21:44:17)
No changes detected
== 生产配置 (21:44:18)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:44:19)
== Docker 镜像 (21:44:20)
构建成功：dc3438b0c9ce
== 全部通过 (21:44:20)
```

演示站已升级（删除的 `moderation/views.py` 在推送后对齐时由 `git pull` 去掉）。

## 没做 / 未验证

- 联赛那种要打几周的赛事，这一行会一直在待办里，直到标记结束
