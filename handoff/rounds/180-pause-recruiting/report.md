# 180 队长停用后，战队自动改成暂不招募（报告）

## 做了什么

1. `teams/services.pause_recruiting(user)`：他当队长、没解散、正在招募的队改成暂不招募（`is_recruiting=False`），重新生成这些战队页；有改动时重新生成战队列表、首页、成员展示（`refresh_team_list`）。返回改了的队
2. `accounts/services.after_deactivation` 取消待审批申请之后调它，并把结果返回
3. `accounts/admin_users.UserEditView`：停用后多一条提示「「X」已改成暂不招募，新队长可以在战队管理页重新打开。」（原来那条「这个账号是「X」的队长…」照旧）
4. 设计 3.7（v6.62）
5. `teams/tests/test_pause_recruiting.py`（4 条）

这样做的理由在 `request.md`：显示「招募中」的地方（战队列表的卡片和筛选、首页、战队页头和资料栏、成员个人页、搜索结果、首页的招募统计）都读 `is_recruiting`，在源头改一次全部跟着对；要是改成每处现算「队长还在不在」，五六个查询各要加子查询。

## 命令输出

变异（测试机，7 处，全部被抓到）：

```
baseline green, 4 tests
caught nothing paused on stopping -> test_only_the_teams_they_captain_and_recruit_for_are_paused
caught nothing paused on stopping -> test_the_recruiting_filters_no_longer_list_it
caught nothing paused on stopping -> test_the_admin_is_told_the_teams_were_paused
caught quiet teams counted too -> test_only_the_teams_they_captain_and_recruit_for_are_paused
caught flag left on -> test_only_the_teams_they_captain_and_recruit_for_are_paused
caught flag left on -> test_the_recruiting_filters_no_longer_list_it
caught team page not redone -> test_only_the_teams_they_captain_and_recruit_for_are_paused
caught list not redone -> test_only_the_teams_they_captain_and_recruit_for_are_paused
caught list redone for nothing -> test_nothing_to_redo_when_nothing_recruits
caught admin not told -> test_the_admin_is_told_the_teams_were_paused
restored and green; missed: none
```

整组检查（测试机）：

```
== pytest (07:40:41)
1692 条测试分成 4 片
分片 1：423 passed in 48.79s
分片 2：423 passed in 41.76s
分片 3：423 passed in 42.47s
分片 4：423 passed in 41.57s
== 迁移 (07:41:34)
No changes detected
== 生产配置 (07:41:36)
System check identified no issues (0 silenced).
== 错误页和模板一致 (07:41:37)
== Docker 镜像 (07:41:38)
构建成功：572a8b06192d
== 全部通过 (07:41:38)
```

演示站升级（`deploy_ship.sh 180`，全量生成成功 46、失败 0，健康检查 ok）后，在服务器上用一个最后回滚的事务停用一支在招募的队的队长、调 `after_deactivation`，看完回滚：

```
队长停用且仍招募的队: []
暂停: ['交大龙骑'] 招募中: False 还在招募筛选里: False
回滚后 招募中: True 队长启用: True
```

第一行说明演示站上现在没有「队长已停用、却还挂着招募中」的队，不用补一次旧数据。

## 没做

- 已经停用了队长、在这轮之前留下来的队不会自动改（没写数据迁移）。演示站上一支都没有；正式站还没上线
- 新队长接手（`assign_captain` 的「你成了队长」邮件）里没提「战队现在暂不招募，可以在管理页打开」。新队长打开管理页就能看到勾选框，暂不加
- 停用的人只是队员时不影响招募：他占着名额，队长可以移出（178）
