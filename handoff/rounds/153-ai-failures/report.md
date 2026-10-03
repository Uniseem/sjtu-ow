# 153 AI 审核调用失败时提醒站长（报告）

## 做了什么

1. `core/admin_todo.py`：`AI_LOOKBACK`（24 小时）、`FAILED_CALL`、`ai_failures()`；`_site_rows()` 有失败时加一行，链到内容审核页
2. 设计 v6.46（14.1）
3. `core/tests/test_admin_functions.py` 加 1 条

## 命令输出

变异（测试机，4 处，第一次全部被抓到）：

```
baseline green, 1 tests
caught yesterday's failures count too -> test_the_owner_hears_when_the_ai_cannot_be_reached
caught every review counts -> test_the_owner_hears_when_the_ai_cannot_be_reached
caught no reason shown -> test_the_owner_hears_when_the_ai_cannot_be_reached
caught no line -> test_the_owner_hears_when_the_ai_cannot_be_reached
restored and green; missed: none
```

整组检查（测试机，1582 条）：

```
== Docker 镜像 (23:27:02)
构建成功：e2445dbd1930
== 全部通过 (23:27:02)
```

演示站（没设 AI 密钥，审核本来就没开，所以没有调用、也没有失败）：

```
(0, '')
```

## 没做 / 未验证

- 「调用失败：」这个前缀是 `moderation/providers.py` 写的，两边靠同一段文字对上；改那边的文字要跟着改这里
