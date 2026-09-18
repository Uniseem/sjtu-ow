# 061 实现报告

## 结论

**完成。** 设计 7.5 的解散限制实现了：战队有有效报名时，队长和超级管理员都不能解散，提示里列出每个挡住的赛事。删掉了没人调用的 `blocked_query()` 占位。

## 实现

`teams.services.disband_blockers(team)`：

- 有效报名：报名状态是待审核、待上游确认或已通过（`tournaments.models.ACTIVE_STATUSES`），**并且**赛事是草稿或已发布
- 每个这样的报名给一条「战队还在赛事「某某」的报名里，请先撤回报名。」
- `disband_team` 原来就会把这些理由拼起来抛错，前台的战队管理页和后台的解散页原来就会把错误显示出来——只是之前理由永远是空的

这也影响 058 的注销：队长要先解散或转让战队，现在解散前还得先撤回有效报名。报名截止后队长不能再撤回（设计 8.5），所以有已通过报名的战队要等赛事结束或取消后才能解散，这和设计一致。

## 测试

`tournaments/tests/test_disband_blockers.py`，11 条：

- 待审核、待上游确认、已通过各挡住一次（提示里有赛事名）
- 超级管理员也被挡
- 草稿赛事的报名也算
- 已驳回、已撤回的不挡
- 赛事已结束、已取消的不挡
- 撤回之后能解散，报名记录还在（软删除的战队仍被引用，设计 7.5）
- 两个赛事都挡时两条理由都列出

## 变异

```
✓ 被抓到 不看报名状态 | 3 failed, 8 passed in 5.89s ['test_a_closed_registration_does_not[rejected]', 'test_a_closed_registration_does_not[withdrawn]']
✓ 被抓到 不看赛事状态 | 2 failed, 9 passed in 5.88s ['test_a_finished_or_cancelled_tournament_does_not[finished]', 'test_a_finished_or_cancelled_tournament_does_not[cancelled]']
✓ 被抓到 草稿赛事不算 | 1 failed, 10 passed in 5.87s ['test_a_draft_tournament_still_counts']
✓ 被抓到 解散时不检查 | 5 failed, 6 passed in 5.89s ['test_a_live_registration_stops_the_captain[pending]', 'test_a_live_registration_stops_the_captain[awaiting_upstream]']
✓ 被抓到 回到占位（永远返回空） | 6 failed, 5 passed in 5.88s ['test_a_live_registration_stops_the_captain[pending]', 'test_a_live_registration_stops_the_captain[awaiting_upstream]']
5/5 被抓到，全部还原
```

## 验收输出

```
$ ruff check . && ruff format --check .
All checks passed!
234 files already formatted

$ uv run python manage.py makemigrations --check --dry-run
No changes detected

$ （生产配置）uv run python manage.py check --deploy
System check identified no issues (0 silenced).

$ uv run python -m pytest -q
824 passed in 52.63s
```

059 推送后的 CI：`success 059: 跑完守卫变异，补上权限和安全类的测试空白`。

## 改动文件

```
teams/services.py                            disband_blockers 实现；删掉 blocked_query
tournaments/tests/test_disband_blockers.py   新建，11 条
handoff/STATUS.md
handoff/rounds/061-disband-blockers/
```
