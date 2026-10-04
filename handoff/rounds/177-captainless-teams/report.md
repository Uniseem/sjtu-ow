# 177 队长被停用的战队，后台提醒站长指定新队长（报告）

## 做了什么

1. `teams/services.py`：`teams_without_captain()`（没解散、没有在用队长的战队：队长停用了或者干脆没有队长）、`captained_teams(user)`
2. `core/admin_todo._site_rows`：超级管理员的待办加「N 支战队的队长账号已停用，没人能审批入队申请、为它报名，去指定新队长」。1 支时链到它的「指定队长」页，多支时链到 `战队列表?captain=gone`
3. `teams/wagtail_hooks.TeamIndexView.get_base_queryset`：`?captain=gone` 时只列这些队
4. `accounts/admin_users.UserEditView`：停用的账号是队长时，多一条提示「这个账号是「X」的队长，到「社区 → 战队」给这些队指定新队长」
5. 设计 v6.60（3.7、14.1）
6. `teams/tests/test_captainless.py`（3 条）

## 命令输出

变异（测试机，6 处，全部被抓到）：

```
baseline green, 3 tests
caught disabled captains still count -> test_which_teams_have_no_working_captain
caught disabled captains still count -> test_the_owner_is_told_and_sent_where_to_fix_it
caught disbanded teams too -> test_which_teams_have_no_working_captain
caught always the whole list -> test_the_owner_is_told_and_sent_where_to_fix_it
caught no to-do row -> test_the_owner_is_told_and_sent_where_to_fix_it
caught the list not filtered -> test_the_owner_is_told_and_sent_where_to_fix_it
caught the edit page says nothing -> test_stopping_a_captain_says_which_teams
restored and green; missed: none
```

整组检查（测试机）：

```
1652 条测试分成 4 片
分片 1：413 passed in 37.71s
分片 2：413 passed in 36.38s
分片 3：413 passed in 44.36s
分片 4：413 passed in 38.23s
== 全部通过 (05:59:37)
```

演示站升级后看现有数据：

```
队长账号停用的战队: 0 []
```

演示站上现在没有这种队，待办里不会出现这一行。

## 没做

- 前台战队页没写「队长账号已停用」：队员看到的队长名字是停用账号的昵称（停用不改昵称），找不到人时只能问社团；指定新队长后自然就对了
- 停用的队长名下还有报名名单的，按 3.7 由管理员在报名审核里处理，没变
