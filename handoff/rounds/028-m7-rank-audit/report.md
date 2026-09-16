# 028 实现报告

## 结论

**完成，没有发现不符。** 附录 A 的 41 个取值（8 大段 × 5 小段 + 前 500 + 未定级）全部对得上，编码和解码双向都对。

## 全表验算

公式：`分数 = 大段序号 × 5 + (5 − 小段)`

```
  bronze         0   1   2   3   4          （5 段 → 1 段）
  silver         5   6   7   8   9
  gold          10  11  12  13  14
  platinum      15  16  17  18  19
  diamond       20  21  22  23  24
  master        25  26  27  28  29
  grandmaster   30  31  32  33  34
  champion      35  36  37  38  39
  top500        40                          （不分小段）

设计举例：钻石 3 = 4×5+(5−3) = 22 → 22 | 显示「钻石 3」
未定级显示 → '未定级'

不一致: 无
```

每一格都验了三件事：

1. `encode_rank(tier, division)` 等于公式算出来的值
2. `decode_rank(分数)` 能还原回 `(tier, division)`
3. 41 个分数严格递增且互不相同

第 3 条是我加的，设计没写。但它是「段位高分数就高」这个前提的直接表达——分队算法整个建立在这上面。

另外确认了两个容易混的边界：

- **未定级存 `None`，不是 0**——0 是「青铜 5」，混了的话未定级的人会被当成最低分参与分队
- **前 500 是 40，比英杰 1 段（39）高一分**

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!

$ uv run python -m pytest -q
546 passed

$ DJANGO_SETTINGS_MODULE=sjtu_ow.settings.prod ... uv run python manage.py check --deploy
System check identified no issues (0 silenced).
```

新增 3 个测试。

## 变异测试

把 `TIER_INDEX[tier] * 5 + (5 - division)` 改成 `... + division`（小段方向反过来，正是最容易写错的那种），三条测试全红：

```
FAILED test_rank_encoding_matches_appendix_a
FAILED test_the_worked_example_from_appendix_a
FAILED test_rank_scores_are_strictly_ordered
```

注意这个改动**不会让任何别的测试变红**——段位仍然是合法的 0–39 整数，仍然能显示，报名仍然能提交，分队仍然能生成。只是分出来的队是歪的。这正是为什么这 41 个数字值得单独钉住。

## 改动文件

```
core/tests/test_chapter15_audit.py   新增附录 A 的 3 个测试
```
