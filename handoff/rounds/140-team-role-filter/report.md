# 140 战队列表按缺的位置筛（报告）

## 做了什么

1. `teams/services.py`：
   - `open_teams(recruiting_only, role, limit)`：有 `role` 时只要招募中、成员数小于上限、`recruiting_roles` 为空或包含这个位置的
   - `_wants(role)`
   - `team_totals(limit)` 在原来的总数之外，同一次聚合里算出 `role_tank` / `role_damage` / `role_support`
2. `teams/views.team_index()`：读 `role` 参数（不认识的当作没有），上限只读一次传下去
3. `teams/index.html`：三个新标签（`data-role-tab`），筛不到时的空状态
4. `core/tests/test_arena_pages.py`：原来断言 `team_totals()` 整个字典，改成只比原来两项，再加上三个位置的数
5. 设计 v6.35（7.6），README 战队一节
6. `teams/tests/test_role_filter.py`（3 条）

第一次实现时位置数量单独查一次、上限又读一次，原有的 `test_team_list_does_not_run_a_query_per_team`（列表页 4 次查询）红了，改成并进同一次聚合后回到 4 次。

## 命令输出

变异（测试机，7 处，第一次全部被抓到）：

```
baseline green, 3 tests
caught the position is ignored -> test_lacking_support_lists_what_a_support_can_join
caught teams wanting anyone are left out -> test_lacking_support_lists_what_a_support_can_join
caught full teams are listed -> test_lacking_support_lists_what_a_support_can_join
caught teams not recruiting are listed -> test_lacking_support_lists_what_a_support_can_join
caught an unknown position filters everything out -> test_an_unknown_role_shows_everything
caught the counts include full teams -> test_lacking_support_lists_what_a_support_can_join
caught no word when nobody lacks it -> test_nobody_lacking_says_so
restored and green; missed: none
```

整组检查（测试机）：

```
1553 条测试分成 4 片
分片 1：389 passed in 33.19s
分片 2：388 passed in 38.06s
分片 3：388 passed in 34.24s
分片 4：388 passed in 33.82s
== 迁移 (21:25:53)
No changes detected
== 生产配置 (21:25:54)
System check identified no issues (0 silenced).
== 错误页和模板一致 (21:25:55)
== Docker 镜像 (21:25:56)
构建成功：ce9309299750
== 全部通过 (21:25:56)
```

演示站升级后，`/teams/?role=support` 的标签：

```
data-role-tab="tank">缺坦克<span class="c-tabs__count">4
data-role-tab="damage">缺输出<span class="c-tabs__count">3
data-role-tab="support">缺支援<span class="c-tabs__count">4
```

## 没做 / 未验证

- 没在手机宽度下看五个标签（`c-tabs` 在手机上横向滚动，13.2.6）
- 预渲染的 `/teams/` 本身也带这三个标签和数量；数量随战队变化时，战队页面原来就会重新生成（`refresh_team_list`）
