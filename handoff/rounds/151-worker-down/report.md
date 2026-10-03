# 151 worker 没在运行时提醒站长（报告）

## 做了什么

1. `core/admin_todo.py`：`_site_rows()` 里调 `check_worker_heartbeat()`，不健康时加一行
2. 设计 v6.44（14.1）
3. `core/tests/test_admin_functions.py` 加 1 条

## 命令输出

变异（测试机，3 处，第一次全部被抓到）：

```
baseline green, 1 tests
caught no line when the worker is down -> test_the_owner_hears_when_the_worker_is_down
caught a line even when it beats -> test_the_owner_hears_when_the_worker_is_down
caught no reason given -> test_the_owner_hears_when_the_worker_is_down
restored and green; missed: none
```

整组检查（测试机）：

```
...
== Docker 镜像 (23:13:13)
构建成功：4d6c5ffe81c3
== 全部通过 (23:13:13)
```

演示站已升级（worker 在运行，所以那里没有这一行）。

## 没做 / 未验证

- 开发环境不跑 worker 时，超级管理员会一直看到这一行（本来就是事实）
